from os import environ, listdir, path, chdir
from click import command, option, echo, secho, style, Group
from pathlib import Path
from sparrow.util import relative_path
import sparrow
from sparrow import get_sparrow_app

from sparrow.ext.pychron import PyChronImporter
from .importer import MAPImporter, NoblesseImporter
from .metadata import MetadataImporter

cli = Group()


def get_data_directory():
    varname = "SPARROW_DATA_DIR"
    env = environ.get(varname, None)
    if env is None:
        v = style(varname, fg="cyan", bold=True)
        echo(f"Environment variable {v} is not set.")
        secho("Aborting", fg="red", bold=True)
        return
    p = Path(env)
    assert p.is_dir()
    print(p)
    return p


@sparrow.task(name="import-map")
def import_map(
    redo: bool = False,
    stop_on_error: bool = False,
    verbose: bool = False,
    show_data: bool = False,
):
    """
    Import WiscAr MAP spectrometer data (ArArCalc files) in bulk.
    """
    data_base = get_data_directory()
    data_path = data_base / "MAP-Irradiations"

    # Make sure we are working in the data directory (for some reason this is important)
    # TODO: fix in sparrow
    chdir(str(data_base))

    app = sparrow.get_app()
    importer = MAPImporter(app, verbose=verbose, show_data=show_data)
    importer.iterfiles(data_path.glob("**/*.xls"), redo=redo)

    # Clean up data inconsistencies
    #fp = relative_path(__file__, "sql", "clean-data.sql")
    db.exec_sql(fp)


@sparrow.task(name="import-noblesse")
def import_noblesse(
    redo: bool = False,
    stop_on_error: bool = False,
    verbose: bool = False,
    show_data: bool = False,
):
    """
    Import WiscAr Noblesse spectrometer data (ArArCalc files) in bulk.
    """
    data_base = get_data_directory()
    data_path = data_base / "Noblesse-test-data"

    # Make sure we are working in the data directory (for some reason this is important)
    # TODO: fix in sparrow
    chdir(str(data_base))

    app = sparrow.get_app()
    importer = NoblesseImporter(app, verbose=verbose, show_data=show_data)
    # TODO: fix for both xls and xlsx files
    importer.iterfiles(data_path.glob("**/*.xlsx"), redo=redo)
    importer.iterfiles(data_path.glob("**/*.xls"), redo=redo)


@sparrow.task()
def import_metadata(verbose: bool = False):
    """
    Import metadata for measurements.
    """
    data_path = get_data_directory()

    fn = data_path / "WiscAr_metadata.xlsx"
    assert fn.exists()

    app = get_sparrow_app()
    app = sparrow.get_app()
    importer = MetadataImporter(app, fn, verbose=verbose)


@sparrow.task(name="import-pychron")
def pychron_import_command(redo: bool = False):
    """Import PyChron Interpreted Age files."""
    app = sparrow.get_app()
    importer = PyChronImporter(app, verbose=True)
    importer.import_all(redo=redo)