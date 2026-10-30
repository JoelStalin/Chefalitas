from decimal import Decimal
import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models")))
from l10n_do_payroll_calculator import (
    calculate_dominican_payroll,
    compute_tss_employee,
    compute_tss_employer,
    compute_dgii_salary_isr,
    DEFAULT_NATIONAL_MIN_WAGE
)

class TestDominicanPayrollCalculation(unittest.TestCase):

    def test_exempt_salary_under_34685(self):
        # Empleado gana RD$ 30,000 mensuales
        salary = Decimal("30000.00")
        res = calculate_dominican_payroll(salary)

        # SFS: 30000 * 3.04% = 912.00
        self.assertEqual(res["sfs_employee"], Decimal("912.00"))
        # AFP: 30000 * 2.87% = 861.00
        self.assertEqual(res["afp_employee"], Decimal("861.00"))
        # Total TSS Empleado: 1773.00
        self.assertEqual(res["total_tss_employee"], Decimal("1773.00"))

        # Base Imponible ISR = 30000 - 1773 = 28227.00
        self.assertEqual(res["taxable_base_isr"], Decimal("28227.00"))
        # ISR = 0.00 (Exento por ser <= 34,685.00)
        self.assertEqual(res["isr_retention"], Decimal("0.00"))

        # Salario Neto = 30000 - 1773 = 28227.00
        self.assertEqual(res["net_salary"], Decimal("28227.00"))
        # Clasificación DGII de tipo de gasto: 01 - Gastos de Personal
        self.assertEqual(res["dgii_expense_type"], "01")

    def test_tier2_isr_retention_salary_45000(self):
        # Empleado gana RD$ 45,000 mensuales
        salary = Decimal("45000.00")
        res = calculate_dominican_payroll(salary)

        # SFS: 45000 * 3.04% = 1368.00
        self.assertEqual(res["sfs_employee"], Decimal("1368.00"))
        # AFP: 45000 * 2.87% = 1291.50
        self.assertEqual(res["afp_employee"], Decimal("1291.50"))
        # Total TSS: 2659.50
        self.assertEqual(res["total_tss_employee"], Decimal("2659.50"))

        # Base imponible = 45000 - 2659.50 = 42340.50
        self.assertEqual(res["taxable_base_isr"], Decimal("42340.50"))
        # Excedente sobre 34,685 = 42340.50 - 34685.00 = 7655.50
        # ISR = 7655.50 * 15% = 1148.33
        self.assertEqual(res["isr_retention"], Decimal("1148.33"))

        # Neto = 45000 - 2659.50 - 1148.33 = 41192.17
        self.assertEqual(res["net_salary"], Decimal("41192.17"))

    def test_tss_caps_on_high_salary(self):
        # Empleado gana RD$ 250,000 mensuales (supera tope de SFS de 10 salarios mínimos)
        salary = Decimal("250000.00")
        res = calculate_dominican_payroll(salary)

        sfs_cap = DEFAULT_NATIONAL_MIN_WAGE * Decimal("10") # 193,525.00
        expected_sfs = (sfs_cap * Decimal("0.0304")).quantize(Decimal("0.01"))
        self.assertEqual(res["sfs_employee"], expected_sfs)

        # AFP tope es 20 salarios mínimos (387,050.00) -> 250,000 no supera el tope
        expected_afp = (salary * Decimal("0.0287")).quantize(Decimal("0.01"))
        self.assertEqual(res["afp_employee"], expected_afp)

    def test_employer_tss_and_infotep_contributions(self):
        # Verificación de aportes patronales (costo de la empresa)
        salary = Decimal("50000.00")
        pat = compute_tss_employer(salary)

        # SFS Patronal 7.09% = 3545.00
        self.assertEqual(pat["sfs_employer"], Decimal("3545.00"))
        # AFP Patronal 7.10% = 3550.00
        self.assertEqual(pat["afp_employer"], Decimal("3550.00"))
        # SRL Patronal 1.20% = 600.00
        self.assertEqual(pat["srl_employer"], Decimal("600.00"))
        # INFOTEP Patronal 1.00% = 500.00
        self.assertEqual(pat["infotep"], Decimal("500.00"))
        # Total costo patronal = 3545 + 3550 + 600 + 500 = 8195.00
        self.assertEqual(pat["total_employer"], Decimal("8195.00"))

if __name__ == "__main__":
    unittest.main()