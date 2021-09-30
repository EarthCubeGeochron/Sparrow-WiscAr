import sparrow
from sparrow.ext.pychron import PyChronImporter


@sparrow.task()
def import_pychron(redo: bool = False):
    """Import PyChron interpreted age files"""
    importer = PyChronImporter(verbose=True)
    importer.import_all("https://github.com/WiscArData", ["NOB-Unknowns"], redo=redo)
