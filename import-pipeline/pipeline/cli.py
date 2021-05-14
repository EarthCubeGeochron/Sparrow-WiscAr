from os import environ, listdir, path
from click import command, option, echo, secho, style, Group
from pathlib import Path
from sparrow import Database
from sparrow.util import relative_path
from sparrow import get_sparrow_app 

from .importer import MAPImporter
from .metadata import MetadataImporter

cli = Group()


def get_data_directory():
    varname = "SPARROW_DATA_DIR"
    env = environ.get(varname, None)
    if env is None:
        v = style(varname, fg='cyan', bold=True)
        echo(f"Environment variable {v} is not set.")
        secho("Aborting", fg='red', bold=True)
        return
    p = Path(env)
    assert p.is_dir()
    return p


@cli.command(name="import-map")
@option('--redo', '-r', is_flag=True, default=False)
@option('--stop-on-error', is_flag=True, default=False)
@option('--verbose', '-v', is_flag=True, default=False)
@option('--show-data', '-S', is_flag=True, default=False)
def import_map(redo=False, stop_on_error=False, verbose=False, show_data=False):
    """
    Import WiscAr MAP spectrometer data (ArArCalc files) in bulk.
    """
    data_path = get_data_directory()/"MAP-Irradiations"

    app = get_sparrow_app()
    db = app.database
    importer = MAPImporter(db, verbose=verbose, show_data=show_data)
    importer.iterfiles(data_path.glob("**/*.xls"), redo=redo)

    # Clean up data inconsistencies
    fp = relative_path(__file__, "sql", "clean-data.sql")
    db.exec_sql(fp)


@cli.command(name="import-metadata")
@option('--redo', '-r', is_flag=True, default=False)
@option('--stop-on-error', is_flag=True, default=False)
@option('--verbose', '-v', is_flag=True, default=False)
def import_metadata(redo=False, stop_on_error=False, verbose=False):
    """
    Import metadata for measurements.
    """
    data_path = get_data_directory()

    fn = (data_path/'WiscAr_metadata.xlsx')
    assert fn.exists()

    app = get_sparrow_app()
    db = app.database
    importer = MetadataImporter(db, fn, verbose=verbose)

if __name__ == '__main__':
    cli()
