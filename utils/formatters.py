"""
Output Formatters
Formats recommendation output for terminal display
"""
from typing import Dict
from tabulate import tabulate
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)


class RecommendationFormatter:
    """Formats recommendation for beautiful terminal output"""

    @staticmethod
    def format_recommendation(recommendation: Dict) -> str:
        """Format complete recommendation for display"""

        output = []

        # Header
        output.append("\n" + "=" * 70)
        output.append(f"{Fore.CYAN}{'RECOMENDACIÓN DE NEGOCIACIÓN':^70}{Style.RESET_ALL}")
        output.append("=" * 70 + "\n")

        # Basic Info
        output.append(f"Service ID: {recommendation['service_id']}")
        output.append(f"Vendor Quote ID: {recommendation['vq_id']}")
        output.append(f"Vendor: {Fore.YELLOW}{recommendation['vendor_name']}{Style.RESET_ALL}")
        output.append(f"Servicio: {recommendation['service_type']} - {recommendation['bandwidth_bps'] / 1_000_000:.0f} Mbps")
        output.append("")

        # Scenarios Table
        output.append("-" * 70)
        output.append(f"{Fore.CYAN}ESCENARIOS DE DESCUENTO{Style.RESET_ALL}")
        output.append("-" * 70 + "\n")

        escenarios_table = RecommendationFormatter._format_scenarios(recommendation['escenarios'])
        output.append(escenarios_table)

        recomendado = recommendation['recomendacion_principal']
        output.append(f"\n{Fore.GREEN}🎯 OBJETIVO PRINCIPAL: Solicitar {recomendado['descuento_pct']:.0f}% de descuento "
                     f"(${recomendado['precio_vendor_final']:,.0f} MRC){Style.RESET_ALL}\n")

        # Vendor History
        output.append("-" * 70)
        output.append(f"{Fore.CYAN}CONTEXTO DEL VENDOR{Style.RESET_ALL}")
        output.append("-" * 70 + "\n")

        vendor_context = RecommendationFormatter._format_vendor_history(
            recommendation['modulo1_vendor_history']
        )
        output.append(vendor_context)

        # Market Position
        output.append("\n" + "-" * 70)
        output.append(f"{Fore.CYAN}POSICIÓN DE MERCADO{Style.RESET_ALL}")
        output.append("-" * 70 + "\n")

        market_context = RecommendationFormatter._format_market_benchmark(
            recommendation['modulo2_market_benchmark'],
            recommendation['modulo3_margin_analysis']['mrc_vendor_cotizado']
        )
        output.append(market_context)

        # Financial Analysis
        output.append("\n" + "-" * 70)
        output.append(f"{Fore.CYAN}ANÁLISIS FINANCIERO{Style.RESET_ALL}")
        output.append("-" * 70 + "\n")

        financial = RecommendationFormatter._format_financial_analysis(
            recommendation['modulo3_margin_analysis'],
            recomendado
        )
        output.append(financial)

        # Arguments
        output.append("\n" + "-" * 70)
        output.append(f"{Fore.CYAN}ARGUMENTOS PARA LA NEGOCIACIÓN{Style.RESET_ALL}")
        output.append("-" * 70 + "\n")

        arguments = RecommendationFormatter._format_arguments(
            recommendation['argumentos_negociacion']
        )
        output.append(arguments)

        # Plan B
        output.append("\n" + "-" * 70)
        output.append(f"{Fore.CYAN}PLAN B{Style.RESET_ALL}")
        output.append("-" * 70 + "\n")

        plan_b = RecommendationFormatter._format_plan_b(recommendation['plan_b'])
        output.append(plan_b)

        # Footer
        output.append("\n" + "=" * 70 + "\n")

        return "\n".join(output)

    @staticmethod
    def _format_scenarios(escenarios: list) -> str:
        """Format scenarios table"""

        headers = ["Escenario", "Descuento", "Precio Vendor", "GM Final", "Prob. Éxito"]
        rows = []

        for esc in escenarios:
            etiqueta = esc['etiqueta']
            if etiqueta == 'RECOMENDADO':
                etiqueta = f"{Fore.GREEN}{etiqueta} ⭐{Style.RESET_ALL}"

            rows.append([
                etiqueta,
                f"{esc['descuento_pct']:.1f}%",
                f"${esc['precio_vendor_final']:,.0f}",
                f"{esc['gm_resultante']:.1f}%",
                f"{esc['probabilidad_exito']*100:.0f}%"
            ])

        return tabulate(rows, headers=headers, tablefmt="grid")

    @staticmethod
    def _format_vendor_history(modulo1: Dict) -> str:
        """Format vendor history section"""

        lines = []
        lines.append("Historial de Negociaciones:")

        if modulo1['total_negotiations'] > 0:
            lines.append(f"  - Descuento promedio otorgado: {modulo1['rango_descuento_historico']['avg']:.1f}%")
            lines.append(f"  - Rango histórico: {modulo1['rango_descuento_historico']['min']:.1f}% - {modulo1['rango_descuento_historico']['max']:.1f}%")
            lines.append(f"  - Tasa de éxito: {modulo1['tasa_exito']*100:.0f}% ({modulo1['total_negotiations']} negociaciones)")
            lines.append(f"  - Tendencia: {modulo1['tendencia']}")
            lines.append(f"  - Score de negociabilidad: {modulo1['vendor_score']}/100")
        else:
            lines.append(f"  {Fore.YELLOW}No hay datos históricos disponibles{Style.RESET_ALL}")

        return "\n".join(lines)

    @staticmethod
    def _format_market_benchmark(modulo2: Dict, precio_actual: float) -> str:
        """Format market benchmark section"""

        lines = []
        lines.append("Benchmark de Precios:")
        lines.append(f"  - Precio cotizado: ${precio_actual:,.0f}")
        lines.append(f"  - Precio promedio mercado: ${modulo2['precio_promedio_mercado']:,.0f}")

        if modulo2['vendors_alternativos']:
            mejor = modulo2['vendors_alternativos'][0]
            lines.append(f"  - Mejor alternativa: ${mejor['precio']:,.0f} ({mejor['vendor']})")

        lines.append(f"  - Gap vs mercado: {modulo2['gap_porcentual']:+.1f}%")
        lines.append(f"  - Percentil: {modulo2['percentil_actual']:.0f}")

        lines.append(f"\n{Fore.YELLOW}🎯 Presión Competitiva: {modulo2['presion_competitiva']}{Style.RESET_ALL}")

        if modulo2['vendors_alternativos']:
            lines.append(f"\nAlternativas Disponibles:")
            for i, alt in enumerate(modulo2['vendors_alternativos'][:3], 1):
                lines.append(f"  {i}. {alt['vendor']}: ${alt['precio']:,.0f} ({alt['ahorro_pct']:.1f}% menos)")

        return "\n".join(lines)

    @staticmethod
    def _format_financial_analysis(modulo3: Dict, recomendado: Dict) -> str:
        """Format financial analysis section"""

        lines = []

        lines.append("Pricing Actual:")
        lines.append(f"  - MRC Cliente (venta): ${modulo3['mrc_cliente']:,.0f}")
        lines.append(f"  - MRC Vendor (cotizado): ${modulo3['mrc_vendor_cotizado']:,.0f}")

        gm_actual_color = Fore.GREEN if modulo3['cumple_target'] else Fore.YELLOW
        lines.append(f"  - Gross Margin actual: {gm_actual_color}{modulo3['gm_actual_pct']:.1f}%{Style.RESET_ALL}")

        lines.append(f"\nObjetivo ({modulo3['target_gm']:.0f}% GM):")
        lines.append(f"  - MRC Vendor máximo: ${modulo3['precio_max_vendor']:,.0f}")
        lines.append(f"  - Ahorro necesario: ${modulo3['ahorro_necesario_usd']:,.0f}")
        lines.append(f"  - Descuento requerido: {modulo3['descuento_necesario_pct']:.1f}%")

        lines.append(f"\nCon Escenario Recomendado ({recomendado['descuento_pct']:.0f}% desc):")
        lines.append(f"  - MRC Vendor final: ${recomendado['precio_vendor_final']:,.0f}")
        lines.append(f"  - Gross Margin: {Fore.GREEN}{recomendado['gm_resultante']:.1f}%{Style.RESET_ALL} ✅")

        return "\n".join(lines)

    @staticmethod
    def _format_arguments(argumentos: list) -> str:
        """Format negotiation arguments"""

        lines = []

        for i, arg in enumerate(argumentos[:5], 1):
            fuerza_color = Fore.RED if arg['fuerza'] == 'ALTA' else Fore.YELLOW if arg['fuerza'] == 'MEDIA' else Fore.WHITE
            lines.append(f"{i}. {arg['titulo']} {fuerza_color}[{arg['fuerza']}]{Style.RESET_ALL}")
            lines.append(f"   \"{arg['argumento']}\"")
            if 'nota' in arg:
                lines.append(f"   {Fore.CYAN}{arg['nota']}{Style.RESET_ALL}")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _format_plan_b(plan_b: Dict) -> str:
        """Format Plan B section"""

        lines = []

        if not plan_b['opciones']:
            return "No hay alternativas disponibles"

        lines.append("Si el vendor NO acepta la recomendación:\n")

        for opcion in plan_b['opciones']:
            lines.append(f"OPCIÓN {opcion['letra']}: {opcion['titulo']}")
            lines.append(f"  → {opcion['descripcion']}")
            lines.append(f"  → Resultado: {opcion['resultado']}")
            lines.append(f"  → Viabilidad: {opcion['viabilidad']}")

            if 'consideraciones' in opcion:
                lines.append(f"  → Consideraciones:")
                for consideracion in opcion['consideraciones']:
                    lines.append(f"     • {consideracion}")

            lines.append("")

        if 'secuencia_recomendada' in plan_b:
            lines.append(f"{Fore.GREEN}🎯 RECOMENDACIÓN: Seguir secuencia {plan_b['secuencia_recomendada']}{Style.RESET_ALL}")

        return "\n".join(lines)
