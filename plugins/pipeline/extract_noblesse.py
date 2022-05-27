from pandas import read_excel, Series
import numpy as N

def value_index(df, value, integer=False):
    for i, row in df.iterrows():
        for j, col in row.iteritems():
            if col != value: continue
            if integer:
                i = df.index.get_loc(i)
                j = df.columns.get_loc(j)
            return (i,j)

def separate_samples(df):
                   
    #identify the instances of Sample: in the file
    ixs = list()
    result = df.isin(["Sample: "])
    series = result.any()
    columnNames = list(series[series == True].index)
    for col in columnNames:
        rows = list(result[col][result[col] == True].index)
        for row in rows:
            ixs.append((row, col))
    #create a dictionary to hold the dataframes for each sample        
    sdf = {}
    #fill the dicitonary
    for i in range(len(ixs)):
        try:
            sdf[i] = (df.loc[ixs[i][0]:ixs[i+1][0]-1,:]
                .dropna(axis=0, how='all')
                .dropna(axis=1, how='all'))
        except:
            sdf[i] = (df.loc[ixs[i][0]:,:]
                .dropna(axis=0, how='all')
                .dropna(axis=1, how='all'))
    return sdf

def analysis_type(df):
    a_label = df.iloc[1,0]
    if "fusion" or "Fusion" in a_label:
        a_type = 'Total Fusion Age'
    else:
        a_type = 'Age Plateau'
    return(a_type)

def sample_info(xdf):
    sample = (xdf.iloc[0:2,:]
            .dropna(axis=0, how='all')
            .dropna(axis=1, how='all'))

    #Remove space from sample:
    sample.iloc[0,0] = 'Sample:'
    
    # Move the J value down into the same column as Sample
    jv = sample.iloc[0:1,2:5]
    jv.columns = [0,1,2]
    sample = sample.iloc[:,0:2]
    sample = sample.append(jv)
    
    for i in range(len(sample.iloc[:,0])):
        sample.iloc[i,0] = sample.iloc[i,0].strip()
    
    #promote first column to index
    sample = sample.set_index(0)
    sample = sample.transpose()
    
        
    return(sample)

def extract_table(xdf):
    #get index of top of the results table
    results = (xdf.iloc[2:,:]
            .dropna(axis=0, how='all'))

    #collapse the two rows of column labels into one
    
    for i in range(len(results.iloc[0,:])):
        if type(results.iloc[0,i]) != float:
            results.iloc[1,i] = results.iloc[0,i] + ' ' + results.iloc[1,i]
        if 'in' in results.iloc[1,i]:
            results.iloc[1,i] = 'in_plateau'

    results = results.iloc[1:,:]
    #find the end of the table and separate that off into its own df
    et = results.iloc[:,0].isna()
    et = list(et[et == True].index)

    age = (results.loc[et[0]:et[0]+1,:]
            .dropna(axis=0, how='all')
            .dropna(axis=1, how='all'))


    #trim that weighted mean age/plateau age off the results table
    results = results.loc[:et[0]-1,:]

    results.columns = results.iloc[0]
    results = results.iloc[1:]
    results.reset_index()

    results['in_plateau'] = results['in_plateau'].notna()
    # Tag age df with unit and error
    if 'Ma' in results.columns:
        age.iloc[0,0] = age.iloc[0,0] + ' Ma'
    else:
        age.iloc[0,0] = age.iloc[0,0] + ' ka'
    
    if '± 2σ (Ma)' or '± 2σ (ka)' in results.columns:
        age.iloc[0,0] = age.iloc[0,0] + ' 2σ'
    else:
        age.iloc[0,0] = age.iloc[0,0] + ' 1σ'

    return(results, age)

def extract_notes(xdf):
    # isolate notes section

    # normal format starts with instrument
    try:
        ixn = value_index(xdf, "Instrument:")
        notes = (df.loc[ixn[0]:ixn[0]+2,:]
                .dropna(axis=0, how='all')
                .dropna(axis=1, how='all'))
        notes.columns = (0,1,2,3)

    # Unusual format starts with J-value
    except:
        try:
            ixn = value_index(xdf, "J-value:")
            notes = (xdf.loc[ixn[0]:ixn[0]+1,:]
                        .dropna(axis=0, how='all')
                    .dropna(axis=1, how='all'))
            notes.columns = (0,1,2,3)
        except:
            # If this isn't the last sample block in the file, it won't have a notes section
            notes = "None"

    #Fine the other three note sections
    ixa = value_index(xdf, "Atmospheric argon ratios ")
    ixb = value_index(xdf, "Interfering isotope production ratios")
    ixc = value_index(xdf, "Decay constants ")

    # Make sure these are present
    if ixa != None:
        
        #Atmospheric argon ratios
        n1 = (df.loc[ixa[0]+1:ixb[0]-1,ixa[1]:ixa[1]+4]
                .dropna(axis=0, how='all')
                .dropna(axis=1, how='all'))
        n1.columns = (0,1,2,3)

        #Interfering Isotope Production Ratios
        try:    
            n2 = (xdf.loc[ixb[0]+1:ixb[0]+5,ixb[1]:ixb[1]+4]
                    .dropna(axis=0, how='all')
                    .dropna(axis=1, how='all'))
            n2.columns = (0,1,2,3)
        except:
            n2 = (xdf.loc[ixb[0]+1:ixb[0]+5,ixb[1]:ixb[1]+4]
                    .dropna(axis=0, how='all')
                    .dropna(axis=1, how='all'))
            n2.columns = (0,1,2)

        #Decay Constants
        n3 = (xdf.loc[ixc[0]+1:,ixc[1]:ixc[1]+4]
                .dropna(axis=0, how='all')
                .dropna(axis=1, how='all'))
        n3.columns=(0,1,2)

        #Combine into one table
        notes = notes.append(n1)
        notes = notes.append(n2)
        notes = notes.append(n3)

        notes = notes.set_index(0)
        notes = notes.transpose()
       
    return(notes)

def extract_noblesse_tables(xdf):
    info = sample_info(xdf)
    data, age = extract_table(xdf)
    notes = extract_notes(xdf)
    return(info, data, age, notes)
    
