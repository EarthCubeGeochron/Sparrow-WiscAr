import numpy as N

from os import environ, listdir, path
from datetime import datetime
from click import command, option, echo, secho, style
from pathlib import Path
from sparrow.database import get_or_create
from sparrow.import_helpers import BaseImporter, SparrowImportError
from pandas import read_excel, isna

def print_dataframe(df):
    secho(str(df.fillna('—'))+'\n', dim=True)

def row_to_mapping(row):
    print(row)
    def get(key):
        v = row['key']
        return v if not isna(v) else None

    return dict(
        location=[get('longitude'), get('latitude')],
        elevation=get('elevation (m)'),

        depth=get('depth (m)'))

def check_matching_irradiation(sample, row):
    # Check that irradiation matches
    try:
        session = sample.session_collection[0]
    except IndexError:
        # Sample is not linked to any sessions, and that's OK!
        return

    irr = session.get_attribute("Irradiation ID")
    # Sessions should not have two Irradiation IDs
    assert len(irr) == 1
    v = irr[0].value
    v1 = str(row['Irradiation'])
    if not v.startswith(v1):
        raise SparrowImportError(f"Irradiation mismatch")
    print(f"  Irradiation {v}")

def format_authorlist(author):
    __ = [a.strip() for a in author.replace(';',',').split(",")]
    if len(__) == 1:
        auths = __[0]
    if len(__) == 2:
        auths = ", ".join(__)
    else:
        auths = __[0]
        if 'et al' not in auths:
            auths += " et al."
    return auths

def parse_doi(link):
    doi = link.split("doi.org/")[-1]
    if doi.startswith("doi:"):
        doi = doi[4:].strip()
    link = None
    if not doi.startswith("10"):
        link = doi
        doi = None
    return doi, link

class MetadataImporter(BaseImporter):
    authority = "WiscAr"
    def __init__(self, db, metadata_file, **kwargs):
        super().__init__(db)
        self.verbose = kwargs.pop("verbose", False)
        self.iterfiles([metadata_file])

    def import_datafile(self, fn, rec, **kwargs):
        """
        Import an original data file
        """
        verbose = self.verbose
        # Extract data tables from Excel sheet

        self.import_sheet(fn, 0)
        self.import_sheet(fn, 1)

    def import_sheet(self, fn, index=0):
        df = read_excel(fn, sheet_name=index)
        n = len(df)
        print(f"{n} rows")
        self.import_samples(df)
        self.import_projects(df)

    def import_samples(self, df):
        # Group everything
        groups = df.groupby("sample_name")
        samples = groups.first()
        # Just get the first of each group for now
        # We might not want to assume sample ID uniqueness
        print(f"{len(samples)} unique sample names")

        # Import individual samples
        for i, row in samples.iterrows():
            try:
                self.import_sample(row)
                self.db.session.commit()
            except SparrowImportError as exc:
                secho(exc.__class__.__name__+": "+str(exc), fg='red')
                self.db.session.rollback()

        self.db.session.flush()

    def import_sample(self, row):
        name = str(row.name)
        sample = self.sample(name=name)
        sample_schema = self.db.interface.sample()
        entity_ref_schema = self.db.interface.sample_geo_entity()

        echo(f"Sample {name}")
        # We need a better way to check creation...
        if sample._created:
            secho(f"  created", fg='yellow')
        else:
            secho(f"  found existing", fg='green')

        n = len(sample.session_collection)
        echo(f"  {n} sessions")

        # Sanity checks
        check_matching_irradiation(sample, row)

        lon = row['longitude']
        lat = row['latitude']
        if not (isna(lon) or isna(lat)):
            loc = self.location(lon,lat)
            print(loc)
            sample.location = loc

        lith = row['lithology']
        if not isna(lith):
            print(lith)
            sample._material = self.material(lith)

        self.db.session.add(sample)
        # This shouldn't be necessary, but it appears to be...
        self.db.session.flush()

        ## Geological entities
        # NOTE: this should probably happen before sample is added, but we
        # couldn't get that to work using the prototype schema-based importing.
        units = []
        # Formations
        fm = row.get("Formation")
        if fm is not None and not isna(fm):
            units.append({
                'name': fm,
                'type': 'formation'
            })

        # Members (even though most aren't actually members in the sheet)
        mbr = row.get("Member")
        if mbr is not None and not isna(mbr):
            units.append({
                'name': mbr,
                'type': 'member (unverified + notes)'
            })

        # Build "linking" model and insert
        for u in units:
            ref = entity_ref_schema.load(
                dict(geo_entity=u, sample=sample),
                session=self.db.session)
            self.db.session.add(ref)
        self.db.session.flush()

    def import_project(self, name, group):
        (paper_title, link) = name
        author = group['author'].unique()[0]
        first_part = paper_title.split(": ")[0]
        title_summary = " ".join(first_part.split()[:8])+"..."
        if not isna(author):
            auths = format_authorlist(author)

            title_summary = auths+" — "+title_summary

        print(title_summary)

        doi, link = parse_doi(link)

        def get(key):
            vals = [v for v in group[key].unique() if not isna(v)]
            if len(vals) == 0:
                return None
            return vals[0]

        p = self.project(name=title_summary)

        pub_data = dict(
            doi=doi,
            title=get('Title'),
            link=link)

        pub = self.db.get_instance("publication", pub_data)
        pub.author = author
        pub.journal = get('journal')
        pub.year = get('year')
        p.publication_collection.append(pub)

        sample_names = [a for a in group.sample_name.unique().astype(str) if not isna(a)]
        if len(sample_names):
            # Link sessions to the project
            q = (self.db.session.query(self.m.session)
                .join(self.m.sample)
                .filter(self.m.sample.name.in_(sample_names)))
            p.session_collection += q
            # Directly link samples (this produces duplicate links which could be
            # an issue)
            q = (self.db.session.query(self.m.sample)
                .filter(self.m.sample.name.in_(sample_names)))
            p.sample_collection += q

        self.db.session.add(p)
        print("")

    def import_projects(self, df):
        # Group by publication for now
        projects = df.groupby(["Title", "doi_link"])
        for name, group in projects:
            try:
                self.import_project(name, group)
                self.db.session.commit()
            except SparrowImportError as exc:
                secho(exc.__class__.__name__+": "+str(exc), fg='red')
                self.db.session.rollback()
