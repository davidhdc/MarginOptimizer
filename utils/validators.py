"""
Input Validators
Validates user inputs and data integrity
"""
from typing import Dict, Tuple


class InputValidator:
    """Validates inputs for the margin optimizer"""

    @staticmethod
    def validate_service_id(service_id: str) -> Tuple[bool, str]:
        """Validate Service ID format"""

        if not service_id or not isinstance(service_id, str):
            return False, "Service ID debe ser un string no vacío"

        # Add specific validation rules as needed
        if len(service_id) < 3:
            return False, "Service ID parece ser inválido (muy corto)"

        return True, ""

    @staticmethod
    def validate_vq_id(vq_id: str) -> Tuple[bool, str]:
        """Validate Vendor Quote ID format (UUID)"""

        if not vq_id or not isinstance(vq_id, str):
            return False, "VQ ID debe ser un string no vacío"

        # Basic UUID validation (can be more strict)
        if len(vq_id) < 32:
            return False, "VQ ID parece ser inválido (debe ser un UUID)"

        return True, ""

    @staticmethod
    def validate_pricing(mrc_cliente: float, mrc_vendor: float) -> Tuple[bool, str]:
        """Validate pricing data"""

        if mrc_cliente <= 0:
            return False, "MRC Cliente debe ser mayor a cero"

        if mrc_vendor <= 0:
            return False, "MRC Vendor debe ser mayor a cero"

        if mrc_vendor >= mrc_cliente:
            return False, f"MRC Vendor (${mrc_vendor:,.0f}) es mayor o igual al MRC Cliente (${mrc_cliente:,.0f}). El margen sería negativo o cero."

        return True, ""

    @staticmethod
    def validate_coordinates(lat: float, lon: float) -> Tuple[bool, str]:
        """Validate geographic coordinates"""

        if not (-90 <= lat <= 90):
            return False, f"Latitud inválida: {lat}. Debe estar entre -90 y 90"

        if not (-180 <= lon <= 180):
            return False, f"Longitud inválida: {lon}. Debe estar entre -180 y 180"

        return True, ""

    @staticmethod
    def validate_bandwidth(bandwidth_bps: int) -> Tuple[bool, str]:
        """Validate bandwidth value"""

        if bandwidth_bps <= 0:
            return False, "Bandwidth debe ser mayor a cero"

        # Typical range check (1 Mbps to 100 Gbps)
        if bandwidth_bps < 1_000_000 or bandwidth_bps > 100_000_000_000:
            return False, f"Bandwidth fuera de rango típico: {bandwidth_bps / 1_000_000:.0f} Mbps"

        return True, ""

    @staticmethod
    def validate_all_inputs(
        service_id: str,
        vq_id: str,
        mrc_cliente: float,
        mrc_vendor: float,
        lat: float,
        lon: float,
        bandwidth_bps: int
    ) -> Tuple[bool, str]:
        """Validate all inputs"""

        validators = [
            InputValidator.validate_service_id(service_id),
            InputValidator.validate_vq_id(vq_id),
            InputValidator.validate_pricing(mrc_cliente, mrc_vendor),
            InputValidator.validate_coordinates(lat, lon),
            InputValidator.validate_bandwidth(bandwidth_bps)
        ]

        for is_valid, error_msg in validators:
            if not is_valid:
                return False, error_msg

        return True, ""
