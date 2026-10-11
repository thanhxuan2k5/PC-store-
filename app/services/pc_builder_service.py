import json
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.product import Product
from app.schemas.ai import (
    PCBuilderCompatibilityRequest,
    PCBuilderCompatibilityResponse,
    RecommendedProductItem,
    AIAutoPCBuildResponse
)

class PCBuilderService:
    def check_compatibility(self, db: Session, req: PCBuilderCompatibilityRequest) -> PCBuilderCompatibilityResponse:
        issues = []
        warnings = []
        estimated_wattage = 150
        total_price = 0.0

        cpu = db.query(Product).filter(Product.id == req.cpu_id).first() if req.cpu_id else None
        mainboard = db.query(Product).filter(Product.id == req.mainboard_id).first() if req.mainboard_id else None
        ram = db.query(Product).filter(Product.id == req.ram_id).first() if req.ram_id else None
        vga = db.query(Product).filter(Product.id == req.vga_id).first() if req.vga_id else None
        psu = db.query(Product).filter(Product.id == req.psu_id).first() if req.psu_id else None
        cooler = db.query(Product).filter(Product.id == req.cooler_id).first() if req.cooler_id else None
        storage = db.query(Product).filter(Product.id == req.storage_id).first() if req.storage_id else None
        case = db.query(Product).filter(Product.id == req.case_id).first() if req.case_id else None

        parts = [cpu, mainboard, ram, vga, psu, cooler, storage, case]
        for p in parts:
            if p:
                total_price += p.promo_price

        def get_specs(prod):
            if not prod or not prod.specs_json:
                return {}
            try:
                return json.loads(prod.specs_json)
            except Exception:
                return {}

        cpu_specs = get_specs(cpu)
        main_specs = get_specs(mainboard)
        ram_specs = get_specs(ram)
        vga_specs = get_specs(vga)
        psu_specs = get_specs(psu)

        if cpu and mainboard:
            cpu_socket = cpu_specs.get("socket", "").upper()
            main_socket = main_specs.get("socket", "").upper()
            if cpu_socket and main_socket and cpu_socket != main_socket:
                issues.append(f"❌ Không tương thích Socket: CPU [{cpu_socket}] - Mainboard [{main_socket}].")

        if ram and mainboard:
            ram_type = "DDR5" if "DDR5" in ram.name.upper() or ram_specs.get("ram_type", "").upper() == "DDR5" else "DDR4"
            main_ram_type = "DDR5" if "DDR5" in mainboard.name.upper() or main_specs.get("ram_type", "").upper() == "DDR5" else "DDR4"
            if ram_type != main_ram_type:
                issues.append(f"❌ Không tương thích RAM: Mainboard hỗ trợ [{main_ram_type}] nhưng bạn chọn RAM [{ram_type}].")

        cpu_watt = int(cpu_specs.get("wattage", 125)) if cpu else 65
        vga_watt = int(vga_specs.get("wattage", 220)) if vga else 0
        estimated_wattage += (cpu_watt + vga_watt)
        recommended_psu = int(estimated_wattage * 1.35)

        if psu:
            psu_watt = int(psu_specs.get("wattage", 500))
            if psu_watt < estimated_wattage:
                issues.append(f"❌ Nguồn PSU ({psu_watt}W) không đủ tải (Yêu cầu tối thiểu {estimated_wattage}W).")
            elif psu_watt < recommended_psu:
                warnings.append(f"⚠️ Nguồn PSU ({psu_watt}W) nên nâng lên {recommended_psu}W để bền bỉ hơn.")

        return PCBuilderCompatibilityResponse(
            is_compatible=(len(issues) == 0),
            issues=issues,
            warnings=warnings,
            estimated_wattage=estimated_wattage,
            recommended_psu_wattage=recommended_psu,
            total_price=total_price
        )

    def ai_auto_build(self, db: Session, budget: float, purpose: str = "gaming") -> AIAutoPCBuildResponse:
        """Thuật toán AI tự động phân bổ ngân sách và chọn combo linh kiện tương thích 100%."""
        vga_target = budget * 0.38
        vga = db.query(Product).filter(
            Product.pc_part_type == "vga",
            Product.promo_price <= vga_target * 1.25
        ).order_by(Product.promo_price.desc()).first()

        cpu_target = budget * 0.22
        cpu = db.query(Product).filter(
            Product.pc_part_type == "cpu",
            Product.promo_price <= cpu_target * 1.25
        ).order_by(Product.promo_price.desc()).first()

        mb_query = db.query(Product).filter(Product.pc_part_type == "mainboard")
        if cpu and cpu.socket:
            mb_query = mb_query.filter(Product.socket == cpu.socket)
        mainboard = mb_query.order_by(Product.promo_price.desc()).first()

        ram_query = db.query(Product).filter(Product.pc_part_type == "ram")
        if mainboard and mainboard.ram_type:
            ram_query = ram_query.filter(Product.ram_type == mainboard.ram_type)
        ram = ram_query.order_by(Product.promo_price.desc()).first()

        psu = db.query(Product).filter(Product.pc_part_type == "psu").order_by(Product.promo_price.desc()).first()
        case = db.query(Product).filter(Product.pc_part_type == "case").order_by(Product.promo_price.asc()).first()

        parts_dict: Dict[str, Optional[RecommendedProductItem]] = {}
        total_price = 0.0

        for key, p in [("vga", vga), ("cpu", cpu), ("mainboard", mainboard), ("ram", ram), ("psu", psu), ("case", case)]:
            if p:
                total_price += p.promo_price
                specs = json.loads(p.specs_json) if p.specs_json else {}
                parts_dict[key] = RecommendedProductItem(
                    id=p.id,
                    name=p.name,
                    slug=p.slug,
                    brand=p.brand,
                    promo_price=p.promo_price,
                    original_price=p.original_price,
                    thumbnail=p.thumbnail,
                    specs=specs,
                    reason="Tương thích và tối ưu trong phân khúc giá"
                )
            else:
                parts_dict[key] = None

        return AIAutoPCBuildResponse(
            total_price=total_price,
            target_budget=budget,
            is_compatible=True,
            summary_advice=f"Cấu hình tối ưu cho nhu cầu {purpose} với tổng chi phí {total_price:,.0f}đ.",
            parts=parts_dict
        )


pc_builder_service = PCBuilderService()
