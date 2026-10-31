from decimal import Decimal, ROUND_HALF_UP

# Salario Mínimo Nacional Promedio del Sector Privado No Sectorizado vigente (para topes TSS)
# Ajustable anualmente según resolución del Comité Nacional de Salarios
DEFAULT_NATIONAL_MIN_WAGE = Decimal("19352.50")

# Topes legales en múltiplos de salarios mínimos según Ley 87-01
SFS_MIN_WAGE_CAP_MULTIPLIER = Decimal("10")
AFP_MIN_WAGE_CAP_MULTIPLIER = Decimal("20")
SRL_MIN_WAGE_CAP_MULTIPLIER = Decimal("4")

# Tasas de la Seguridad Social (TSS)
TSS_RATE_SFS_EMPLOYEE = Decimal("0.0304")   # 3.04%
TSS_RATE_AFP_EMPLOYEE = Decimal("0.0287")   # 2.87%

TSS_RATE_SFS_EMPLOYER = Decimal("0.0709")   # 7.09%
TSS_RATE_AFP_EMPLOYER = Decimal("0.0710")   # 7.10%
TSS_RATE_SRL_EMPLOYER = Decimal("0.0120")   # 1.20% (promedio de riesgos laborales)
INFOTEP_RATE_EMPLOYER = Decimal("0.0100")   # 1.00%

# Escala Progresiva Mensual de Retención de ISR para Asalariados (DGII art. 296 Código Tributario)
DGII_ISR_TIER1_MAX = Decimal("34685.00")    # RD$ 416,220.00 anual / 12
DGII_ISR_TIER2_MAX = Decimal("52027.42")    # RD$ 624,329.00 anual / 12
DGII_ISR_TIER3_MAX = Decimal("72260.25")    # RD$ 867,123.00 anual / 12

DGII_ISR_TIER2_FIXED = Decimal("0.00")
DGII_ISR_TIER3_FIXED = Decimal("2601.36")
DGII_ISR_TIER4_FIXED = Decimal("6647.92")

DGII_ISR_RATE_TIER2 = Decimal("0.15")       # 15%
DGII_ISR_RATE_TIER3 = Decimal("0.20")       # 20%
DGII_ISR_RATE_TIER4 = Decimal("0.25")       # 25%

def round_curr(val: Decimal) -> Decimal:
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def compute_tss_employee(gross_salary: Decimal, min_wage: Decimal = DEFAULT_NATIONAL_MIN_WAGE) -> dict:
    """Calcula retenciones TSS a cargo del empleado con topes legales."""
    sfs_cap = min_wage * SFS_MIN_WAGE_CAP_MULTIPLIER
    afp_cap = min_wage * AFP_MIN_WAGE_CAP_MULTIPLIER

    sfs_base = min(gross_salary, sfs_cap)
    afp_base = min(gross_salary, afp_cap)

    sfs = round_curr(sfs_base * TSS_RATE_SFS_EMPLOYEE)
    afp = round_curr(afp_base * TSS_RATE_AFP_EMPLOYEE)

    return {
        "sfs": sfs,
        "afp": afp,
        "total_tss": sfs + afp,
        "sfs_base": sfs_base,
        "afp_base": afp_base,
    }

def compute_tss_employer(gross_salary: Decimal, min_wage: Decimal = DEFAULT_NATIONAL_MIN_WAGE) -> dict:
    """Calcula aportes patronales TSS e INFOTEP con topes legales."""
    sfs_cap = min_wage * SFS_MIN_WAGE_CAP_MULTIPLIER
    afp_cap = min_wage * AFP_MIN_WAGE_CAP_MULTIPLIER
    srl_cap = min_wage * SRL_MIN_WAGE_CAP_MULTIPLIER

    sfs_base = min(gross_salary, sfs_cap)
    afp_base = min(gross_salary, afp_cap)
    srl_base = min(gross_salary, srl_cap)

    sfs_employer = round_curr(sfs_base * TSS_RATE_SFS_EMPLOYER)
    afp_employer = round_curr(afp_base * TSS_RATE_AFP_EMPLOYER)
    srl_employer = round_curr(srl_base * TSS_RATE_SRL_EMPLOYER)
    infotep = round_curr(gross_salary * INFOTEP_RATE_EMPLOYER)

    total_employer = sfs_employer + afp_employer + srl_employer + infotep

    return {
        "sfs_employer": sfs_employer,
        "afp_employer": afp_employer,
        "srl_employer": srl_employer,
        "infotep": infotep,
        "total_employer": total_employer,
    }

def compute_dgii_salary_isr(taxable_base: Decimal) -> Decimal:
    """Calcula la retención de ISR mensual de asalariados según escala art. 296 DGII."""
    if taxable_base <= DGII_ISR_TIER1_MAX:
        return Decimal("0.00")
    elif taxable_base <= DGII_ISR_TIER2_MAX:
        excess = taxable_base - DGII_ISR_TIER1_MAX
        return round_curr(DGII_ISR_TIER2_FIXED + (excess * DGII_ISR_RATE_TIER2))
    elif taxable_base <= DGII_ISR_TIER3_MAX:
        excess = taxable_base - DGII_ISR_TIER2_MAX
        return round_curr(DGII_ISR_TIER3_FIXED + (excess * DGII_ISR_RATE_TIER3))
    else:
        excess = taxable_base - DGII_ISR_TIER3_MAX
        return round_curr(DGII_ISR_TIER4_FIXED + (excess * DGII_ISR_RATE_TIER4))

def calculate_dominican_payroll(gross_salary: Decimal, min_wage: Decimal = DEFAULT_NATIONAL_MIN_WAGE, other_deductions: Decimal = Decimal("0.00"), is_exempt: bool = False) -> dict:
    """
    Calcula una nómina completa dominicana:
    Sueldo Bruto -> TSS Empleado -> Base Imponible ISR -> Retención ISR -> Aportes Patronales -> Neto a Pagar.
    """
    tss_emp = compute_tss_employee(gross_salary, min_wage)
    taxable_base = max(Decimal("0.00"), gross_salary - tss_emp["total_tss"])

    isr_retention = Decimal("0.00") if is_exempt else compute_dgii_salary_isr(taxable_base)
    tss_pat = compute_tss_employer(gross_salary, min_wage)

    total_employee_deductions = tss_emp["total_tss"] + isr_retention + other_deductions
    net_salary = gross_salary - total_employee_deductions
    total_company_cost = gross_salary + tss_pat["total_employer"]

    return {
        "gross_salary": gross_salary,
        "sfs_employee": tss_emp["sfs"],
        "afp_employee": tss_emp["afp"],
        "total_tss_employee": tss_emp["total_tss"],
        "taxable_base_isr": taxable_base,
        "isr_retention": isr_retention,
        "other_deductions": other_deductions,
        "total_deductions": total_employee_deductions,
        "net_salary": net_salary,
        "sfs_employer": tss_pat["sfs_employer"],
        "afp_employer": tss_pat["afp_employer"],
        "srl_employer": tss_pat["srl_employer"],
        "infotep": tss_pat["infotep"],
        "total_employer_contributions": tss_pat["total_employer"],
        "total_company_cost": total_company_cost,
        "dgii_expense_type": "01", # 01 - Gastos de Personal
    }