from sys import exit
from os import environ, listdir, path
from datetime import datetime
from click import command, option, echo, secho, style
from pathlib import Path

from pandas import read_excel
#from plugins.pipeline.extract_noblesse import sample_info
from sparrow.database import get_or_create
from sparrow.import_helpers import BaseImporter, SparrowImportError
from IPython import embed

from .extract_tables import extract_data_tables
from .extract_noblesse import separate_samples, extract_noblesse_tables, analysis_type

def print_dataframe(df):
    secho(str(df.fillna(''))+'\n', dim=True)

param_data = {
    'Tstep': "Temperature of heating step",
    'power': "Laser power of heating step",
    '36Ar(a)': "36Ar, corrected for air interference",
    '36Ar (cps)': "36Ar counts per second",
    '37Ar(ca)': "37Ar, corrected for Ca interference",
    '37Ar (cps)': "37Ar counts per second",
    '38Ar(cl)': "38Ar, corrected for Cl interference",
    '39Ar(k)': "39Ar, corrected for amount produced by K",
    '39Ar (cps)': "39Ar counts per second",
    '40Ar(r)': "Radiogenic 40Ar measured abundance",
    '40Ar (cps)': "40Ar counts per second",
    '40(r)/39(k)': "Ratio of radiogenic 40Ar to 39Ar from K",
    '40Ar*/39ArK': "Ratio of radiogenic 40Ar to 39Ar from K",
    'step_age': "Age calculated for a single heating step",
    'plateau_age': "Age calculated for a plateau",
    'total_fusion_age': "Age calculated for fusion of all heating steps",
    '40Ar(r) [%]': "Radiogenic 40Ar, percent released in this step",
    '%40Ar*': "Radiogenic 40Ar, percent released in this step",
    '39Ar(k) [%]': "39Ar from potassium, percent released in this step",
    'K/Ca': "Potassium/Calcium ratio"
}

def split_error(v):
    a = v.replace("Ma","").split("±")
    value = float(a[0].strip())
    error = float(a[1].strip())
    return value, error

class NoblesseImporter(BaseImporter):
    authority = "WiscAr"
    file_type = "Noblesse"
    def __init__(self, db, **kwargs):
        self.show_data = kwargs.pop('show_data', False)
        super().__init__(db, **kwargs)
        self.create_parameters()

    def create_parameters(self):
        for k,v in param_data.items():
            p = self.parameter(k, v)
            self.add(p)
        # Create error metrics
        V = self.unit('V', 'Measured isotope abundance')
        C = self.unit('cps', 'Counts per second')
        em1 = self.error_metric('1s', '1 standard deviation')
        em2 = self.error_metric('2s', '2 standard deviations')

        at1 = self.analysis_type("Total Fusion Age", "Integrated Age")
        at2 = self.analysis_type("Plateau Age", "Integrated Age")

        # Set the description for the data file type
        v = self.db.session.query(self.m.data_file_type).get(self.file_type)
        v.description = 'Formatted Excel Spreadsheet'

        self.add(v, V, C, em1, em2, at1, at2)
    
    def import_datafile(self, fn, rec, **kwargs):
        """
        Import an original data file
        """

        mod_time = datetime.fromtimestamp(path.getmtime(fn))
        
        df = read_excel(fn, header = None)
        a_type = analysis_type(df)

        sample_set = separate_samples(df)
            
        for i in range(len(sample_set)):
            try:
                info, data, age, notes = extract_noblesse_tables(sample_set[i])
            except:
                raise SparrowImportError(str())
            
            #if self.show_data:
                #print_dataframe(data)
                #print_dataframe(age)
                #print_dataframe(info)
                #print_dataframe(notes)
            
            
            sn = info.pop('Sample:')
            sample = self.sample(name=sn[1])
            mat = info.pop('Material:') 
            target = self.material(mat[1])
            instrument = self.db.get_or_create(
            self.m.instrument,
            name="Noblesse 5-collector mass spectrometer")
                        
            method = self.method("Ar/Ar "+ a_type)
            self.add(sample, target, instrument, method)
            self.db.session.flush()

            session = self.db.get_or_create(
                self.m.session,
                sample_id=sample.id,
                instrument=instrument.id,
                technique=method.id,
                date=mod_time,
                target=target.id)
            session.date_precision = "day"
            self.add(session)
            self.db.session.flush()


            info = self.general_info(session, info, notes)
            session.data = info.to_dict()    
        
            for i, step in enumerate(data.iterrows()):
                self.import_heating_step(i, step, session, data)

            self.import_age(session, a_type, age)    

                # This function returns the top-level
                # record that should be linked to the datafile
            self.db.session.flush()
            yield session   
        
            for i, step in enumerate(data.iterrows()):
                self.import_heating_step(i, step, session, data)

            self.import_age(session, a_type, age)    

            # This function returns the top-level
            # record that should be linked to the datafile
            self.db.session.flush()
            yield session
    
    def general_info(self, session, info, notes):
        analysis = self.add_analysis(session, "General information")
        
        # J-value
        try:
            value, error = info.pop('J-value:')
            self.datum(analysis, "J-value", value, error=error)
        except:
            value, error = notes.pop('J-value:')
            self.datum(analysis, "J-value", value, error=error)
      
        # FC or AC tuff age
        try:
            std = notes.pop('Standard:')
            value, error = notes.pop('Standard age (Ma):')
            self.constant(analysis, std+" standard age",
                    value,
                    error=error,
                    unit='Ma')
        except:
            pass
               
        self.db.session.flush()
        return info
    
    def import_heating_step(self, i, step, session, data):
        (ix, row) = step

        analysis = self.add_analysis(session, "Heating step",
            analysis_name= row['File'],
            session_index=i)
        analysis.in_plateau = row['in_plateau']
        analysis.is_interpreted = False
        self.add(analysis)

        try:
            self.datum(analysis, 'power', row['Laser Power'], unit='%',
                    description='Laser power for heating step')

        except:
            pass
            
        for param in ['40Ar (cps)','39Ar (cps)','37Ar (cps)','36Ar (cps)',
                  '40Ar*/39ArK','%40Ar*']:
            unit = 'cps'
            if '*' in param:
                unit = 'V'
            if '/' in param:
                unit = 'ratio'
            self.datum(analysis, param, row[param],
                unit=unit, description=param_data[param])

        try:
            ix = list(row.index).index('Age (Ma)')
            error_ix = ix+1
            em = self.get_error_metric(row.index[error_ix])
            self.datum(analysis, 'step_age', row['Age (Ma)'],
                unit='Ma',
                error=row.iloc[error_ix],
                error_metric=em,
                error_unit='Ma')
            age_unit = 'Ma'
        except:
            ix = list(row.index).index('Age (ka)')
            error_ix = ix+1
            em = self.get_error_metric(row.index[error_ix])
            self.datum(analysis, 'step_age', row['Age (ka)'],
                unit='Ma',
                error=row.iloc[error_ix],
                error_metric=em,
                error_unit='Ma')
            age_unit = 'ka'

        self.add_K_Ca_ratio(analysis, row)
        self.db.session.flush()
        return age_unit

    def get_error_metric(self, label):
        return label.replace("± ","")

    def add_K_Ca_ratio(self, analysis, row):
        ix = list(row.index).index('K/Ca')
        self.datum(analysis, 'K/Ca', row['K/Ca'],
            unit='ratio')

    def import_age(self, session, a_type, age, **kwargs):
        if a_type == 'Total Fusion Age':
            age_parameter = 'total_fusion_age'
        
            analysis = self.analysis(
                session_id = session.id,
                is_interpreted=True,
                type='Total Fusion Age')
        else:
            age_parameter = 'plateau_age'
        
            analysis = self.analysis(
                session_id = session.id,
                is_interpreted=True,
                type='Age Plateau')
                
        ax = age.iloc[0,1]
        ae = age.iloc[0,2]

        if 'Ma' in age.iloc[0,0]:
            age_unit = 'Ma'
        else:
            age_unit = 'ka'
        
        if '2σ' in age.iloc[0,0]:
            em = '2σ'
        
        
        #row = self.import_shared_parameters(analysis, row)
        self.datum(analysis,
            value=ax,
            unit=age_unit,
            parameter=age_parameter,
            error=ae,
            error_metric=em,
            is_computed=True,
            error_unit=age_unit,
            **kwargs)


class MAPImporter(BaseImporter):
    authority = "WiscAr"
    file_type = "ArArCALC"
    def __init__(self, db, **kwargs):
        self.show_data = kwargs.pop('show_data', False)
        super().__init__(db, **kwargs)
        self.create_parameters()

    def irradiation(self, id):
        irr = self.db.get_or_create(self.m.irradiation,
            id=id)
        irr.title = id
        return irr

    def create_parameters(self):
        for k,v in param_data.items():
            p = self.parameter(k, v)
            self.add(p)
        # Create error metrics
        V = self.unit('V', 'Measured isotope abundance')
        em1 = self.error_metric('1s', '1 standard deviation')
        em2 = self.error_metric('2s', '2 standard deviations')

        at1 = self.analysis_type("Total Fusion Age", "Integrated Age")
        at2 = self.analysis_type("Plateau Age", "Integrated Age")

        # Set the description for the data file type
        v = self.db.session.query(self.m.data_file_type).get(self.file_type)
        v.description = 'Excel spreadsheet for the ArArCALC data analysis program.'

        self.add(v, V, em1, em2, at1, at2)

    def import_datafile(self, fn, rec, **kwargs):
        """
        Import an original data file
        """
        # Extract data tables from Excel sheet

        # File modification time is right now the best proxy
        # for creation date (note: sessions will be duplicated
        # if input files are changed)
        mod_time = datetime.fromtimestamp(path.getmtime(fn))

        try:
            incremental_heating, info, results = extract_data_tables(fn)
        except Exception as exc:
            raise SparrowImportError(str(exc))
        if self.show_data:
            print_dataframe(incremental_heating)
            print_dataframe(info)
            print_dataframe(results.transpose())

        sample = self.sample(name=info.pop('Sample'))
        target = self.material(info.pop('Material'))
        instrument = self.db.get_or_create(
            self.m.instrument,
            name="MAP 215-50")
        method = self.method("Ar/Ar "+info.pop("Type"))
        self.add(sample, target, instrument, method)
        self.db.session.flush()

        session = self.db.get_or_create(
            self.m.session,
            sample_id=sample.id,
            instrument=instrument.id,
            technique=method.id,
            date=mod_time,
            target=target.id)
        session.date_precision = "day"
        self.add(session)
        self.db.session.flush()


        info = self.general_info(session, info)
        session.data = info.to_dict()

        for i, step in enumerate(incremental_heating.iterrows()):
            self.import_heating_step(i, step, session, incremental_heating)

        # Import results table
        try:
            res = results.loc["Age Plateau"]
            self.import_age_plateau(session, res)
        except KeyError:
            pass

        res = results.loc["Total Fusion Age"]
        self.import_fusion_age(session, res)

        # This function returns the top-level
        # record that should be linked to the datafile
        self.db.session.flush()
        yield session

    def general_info(self, session, info):
        analysis = self.add_analysis(session, "General information")
        self.attribute(analysis, "Irradiation ID", info.pop('Project'))
        # J-value
        try:
            value, error = split_error(info.pop('J'))
            self.datum(analysis, "J-value", value, error=error)
        except:
            self.datum(analysis, "J-value", info.pop('J-value'))
      
        # Location
        self.attribute(analysis, "Irradiation location", info.pop('Location'))
        # Analyst
        self.attribute(analysis, "Analyst", info.pop('Analyst'))
        try:
            self.attribute(analysis, "Mass Discrimination Law", info.pop('Mass Discrimination Law'))
        except:
            self.attribute(analysis, "Mass Discrimination Law", 'None')

        # FC or AC tuff age
        try:
            for c in ['FC', 'AC', 'FCs']:
                try:
                    std = info.pop(c)
                except KeyError:
                    continue
                value, error = split_error(std)
                # Correct inconsistencies in our method
                if value > 28 and value < 29:
                    c = 'FC'
                if value > 1.1 and value < 1.2:
                    c = 'AC'

                self.constant(analysis, c+" standard age",
                    value,
                    error=error,
                    unit='Ma')
                break
        except:
            std = info.pop('Standard')
            # Correct inconsistencies in our method
            if std > 28 and std < 29:
                c = 'FC'
            if std > 1.1 and std < 1.2:
                c = 'AC'
            error='None'
            self.constant(analysis, c+" standard age",
                    value,
                    error=error,
                    unit='Ma')

        self.db.session.flush()
        return info

    def import_heating_step(self, i, step, session, incremental_heating):
        (ix, row) = step

        analysis = self.add_analysis(session, "Heating step",
            analysis_name=ix,
            session_index=i)
        analysis.in_plateau = row['in_plateau']
        analysis.is_interpreted = False
        self.add(analysis)

        # Heuristic to check whether we are measuring
        # laser power or temperature
        s = incremental_heating['temperature']
        if (s<=100).sum() == len(s):
            # Everything is less than 100
            self.datum(analysis, 'power', row['temperature'], unit='%',
                description='Laser power for heating step')

        else:
            self.datum(analysis, 'Tstep', row['temperature'],
                unit="°C", description='Temperature of heating step')

        for param in ['36Ar(a)','37Ar(ca)','38Ar(cl)','39Ar(k)',
                  '40Ar(r)','39Ar(k) [%]','40Ar(r) [%]']:
            unit = 'V'
            if '[%]' in param:
                unit = '%'
            self.datum(analysis, param, row[param],
                unit=unit, description=param_data[param])

        ix = list(row.index).index('Age')
        error_ix = ix+1
        em = self.get_error_metric(row.index[error_ix])
        self.datum(analysis, 'step_age', row['Age'],
            unit='Ma',
            error=row.iloc[error_ix],
            error_metric=em,
            error_unit='Ma')

        self.add_K_Ca_ratio(analysis, row)
        self.db.session.flush()

    def get_error_metric(self, label):
        return label.replace("± ","")

    def add_K_Ca_ratio(self, analysis, row):
        ix = list(row.index).index('K/Ca')
        error_ix = ix+1
        em = self.get_error_metric(row.index[error_ix])
        self.datum(analysis, 'K/Ca', row['K/Ca'],
            unit='ratio',
            error=row.iloc[error_ix],
            error_metric=em,
            error_unit='ratio')

    def import_age_plateau(self, session, row):
        analysis = self.analysis(
            session_id = session.id,
            is_interpreted=True,
            type='Age Plateau')
        row = self.import_shared_parameters(analysis, row)

        parameter = self.parameter('39Ar(k) plateau [%]')
        parameter.description="39Ar from potassium, cumulative percent released in all plateau steps"
        self.add(parameter)

        self.datum(analysis, parameter.id, row.pop('39Ar(k)'),
            unit='%',
            is_interpreted=True,
            is_computed=True)

        analysis.data = row.dropna().to_dict()
        self.add(analysis)

    def import_fusion_age(self, session, row):

        analysis = self.analysis(
            session_id = session.id,
            is_interpreted=True,
            type='Total Fusion Age')
        row = self.import_shared_parameters(analysis, row)
        analysis.data = row.dropna().to_dict()
        self.add(analysis)

    def import_shared_parameters(self, analysis, row, **kwargs):
        self.add_K_Ca_ratio(analysis, row)

        age_parameter = 'plateau_age'
        if analysis.analysis_type == 'Total Fusion Age':
            age_parameter = 'total_fusion_age'

        ix = list(row.index).index('Age')
        error_ix = ix+1
        em = self.get_error_metric(row.index[error_ix])

        # TODO: integrate this new method
        # Datum = self.db.app.interface.datum()
        #
        # datum = dict(
        #     analysis=analysis,
        #     value=row['Age'],
        #     error=row.iloc[error_ix],
        #     unit='Ma',
        #     error_unit='Ma',
        #     type=dict(
        #         parameter=age_parameter,
        #         is_computed=True,
        #         error_metric=em
        #     )
        # )
        #
        # Datum.load(datum, session=self.db.session)
        #
        self.datum(analysis,
            value=row['Age'],
            unit='Ma',
            parameter=age_parameter,
            error=row.iloc[error_ix],
            error_metric=em,
            is_computed=True,
            error_unit='Ma',
            **kwargs)

        ## 40Ar/39Ar(k) ratio
        param = '40(r)/39(k)'
        ix = list(row.index).index(param)
        error_ix = ix+1
        el = row.index[error_ix]
        em = self.get_error_metric(el)
        self.datum(analysis, param, row[param],
            unit='ratio',
            error=row.iloc[error_ix],
            error_metric=em,
            is_interpreted=True,
            is_computed=True,
            error_unit='ratio')

        row.drop(index=['Age','K/Ca', param, el], inplace=True)
        return row