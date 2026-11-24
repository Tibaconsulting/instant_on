"""HPE Networking Instant On hardware SKU and model catalog."""

from __future__ import annotations

# Mapping from HPE Instant On SKU (part number) to official marketing model name.
SKU_TO_MODEL: dict[str, str] = {
    # Wi-Fi 5 (802.11ac Wave 2) Access Points
    "R2W95A": "AP11",
    "R2W96A": "AP11",
    "R2W97A": "AP11",
    "R2W98A": "AP11",
    "R2W99A": "AP11",
    "R2X15A": "AP11D",
    "R2X16A": "AP11D",
    "R2X17A": "AP11D",
    "R2X18A": "AP11D",
    "R2X19A": "AP11D",
    "R2X00A": "AP12",
    "R2X01A": "AP12",
    "R2X02A": "AP12",
    "R2X03A": "AP12",
    "R2X04A": "AP12",
    "R2X05A": "AP15",
    "R2X06A": "AP15",
    "R2X07A": "AP15",
    "R2X08A": "AP15",
    "R2X09A": "AP15",
    "R2X10A": "AP17",
    "R2X11A": "AP17",
    "R2X12A": "AP17",
    "R2X13A": "AP17",
    "R2X14A": "AP17",
    # Wi-Fi 6 / 6E Access Points
    "S1T08A": "AP21",
    "S1T09A": "AP21",
    "S1T10A": "AP21",
    "S1T11A": "AP21",
    "S1T12A": "AP21",
    "R4W01A": "AP22",
    "R4W02A": "AP22",
    "R4W03A": "AP22",
    "R4W04A": "AP22",
    "R4W05A": "AP22",
    "S1U75A": "AP22D",
    "S1U76A": "AP22D",
    "S1U77A": "AP22D",
    "S1U78A": "AP22D",
    "S1U79A": "AP22D",
    "R9B27A": "AP25",
    "R9B28A": "AP25",
    "R9B29A": "AP25",
    "R9B30A": "AP25",
    "R9B31A": "AP25",
    "S1T36A": "AP27",
    "S1T37A": "AP27",
    "S1T38A": "AP27",
    "S1T39A": "AP27",
    "S1T40A": "AP27",
    "S1T22A": "AP32",
    "S1T23A": "AP32",
    "S1T24A": "AP32",
    "S1T25A": "AP32",
    "S1T26A": "AP32",
    # 1830 Switch Series
    "JL810A": "1830 8G",
    "JL811A": "1830 8G 4p Class4 PoE 65W",
    "JL812A": "1830 24G 2SFP",
    "JL813A": "1830 24G 12p Class4 PoE 2SFP 195W",
    "JL814A": "1830 48G 4SFP",
    "JL815A": "1830 48G 24p Class4 PoE 4SFP 370W",
    # 1930 Switch Series
    "JL680A": "1930 8G 2SFP",
    "JL681A": "1930 8G Class4 PoE 2SFP 124W",
    "JL682A": "1930 24G 4SFP/SFP+",
    "JL683A": "1930 24G Class4 PoE 4SFP/SFP+ 195W",
    "JL683B": "1930 24G Class4 PoE 4SFP/SFP+ 195W",
    "JL684A": "1930 24G Class4 PoE 4SFP/SFP+ 370W",
    "JL684B": "1930 24G Class4 PoE 4SFP/SFP+ 370W",
    "JL685A": "1930 48G 4SFP/SFP+",
    "JL686A": "1930 48G Class4 PoE 4SFP/SFP+ 370W",
    "JL686B": "1930 48G Class4 PoE 4SFP/SFP+ 370W",
    # 1960 Switch Series
    "JL805A": "1960 12XGT 4SFP+",
    "JL806A": "1960 24G 2XGT 2SFP+",
    "JL807A": "1960 24G 20p Class4/4p Class6 PoE 2XGT 2SFP+ 370W",
    "JL808A": "1960 48G 2XGT 2SFP+",
    "JL809A": "1960 48G 40p Class4/8p Class6 PoE 2XGT 2SFP+ 600W",
    # Secure Gateways
    "S0G18A": "SG1004",
    "S0G19A": "SG2505P",
}

# Fallback mapping from internal Aruba hardware model to Instant On marketing name.
HW_MODEL_TO_MARKETING: dict[str, str] = {
    "AP-303": "AP11",
    "AP-303H": "AP11D",
    "AP-305": "AP12",
    "AP-315": "AP15",
    "AP-365": "AP17",
    "AP-503": "AP21",
    "AP-505": "AP22",
    "AP-505H": "AP22D",
    "AP-515": "AP25",
    "AP-565": "AP27",
    "AP-615": "AP32",
}


def resolve_device_model(
    sku: str | None, hw_model: str | None, device_type: str | None = None
) -> tuple[str | None, str | None]:
    """Return (marketing_model, model_id) for Home Assistant DeviceInfo."""
    sku_clean = (sku or "").strip().upper() or None
    hw_clean = (hw_model or "").strip() or None

    marketing = (
        SKU_TO_MODEL.get(sku_clean) if sku_clean else None
    ) or (
        HW_MODEL_TO_MARKETING.get(hw_clean) if hw_clean else None
    )

    id_parts = [p for p in (hw_clean, sku_clean) if p and p != marketing]
    # Deduplicate when sku == hw_model (e.g. JL813A)
    unique_id_parts = list(dict.fromkeys(id_parts))
    model_id = " / ".join(unique_id_parts) if unique_id_parts else None

    if marketing:
        return marketing, model_id
    return hw_clean or sku_clean or device_type, None
