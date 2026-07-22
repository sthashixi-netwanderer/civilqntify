"""Material Quantification Module — Bill of Quantities from Mix Design.

Takes concrete mix design proportions (from Module 1) and calculates
total project material quantities based on element dimensions or volume.

Usage:
    from material_quantify import MaterialQuantifier, StructuralElement
    from material_quantify.models import MixDesignTransferData

    td = MixDesignTransferData.from_mix_design_result(result)
    q = MaterialQuantifier(td)
    bill = q.quantify_by_volume(25.0, wastage_percent=5.0)
    print(bill.format_report())
"""

from material_quantify.engine.quantifier import MaterialQuantifier
from material_quantify.models.bill import MaterialBill
from material_quantify.models.elements import StructuralElement
from material_quantify.models.transfer_data import MixDesignTransferData

__all__ = [
    "MaterialQuantifier",
    "MaterialBill",
    "StructuralElement",
    "MixDesignTransferData",
]
