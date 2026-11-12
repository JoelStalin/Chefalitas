{
    "name": "Nómina Dominicana - TSS & DGII (IR-3 / IR-4)",
    "summary": """
        Gestión integral de nómina dominicana: cálculo automático de deducciones de ley TSS
        (SFS 3.04%, AFP 2.87%), escala progresiva de ISR de asalariados (DGII art. 296),
        aportes patronales (SFS 7.09%, AFP 7.10%, SRL 1.20%, INFOTEP 1.00%) y contabilización
        automática al tipo de gasto DGII 01 (Gastos de Personal).
    """,
    "author": "Joel S. Martinez / GetUpSoft",
    "company": "GetUpSoft",
    "category": "Human Resources/Payroll",
    "license": "LGPL-3",
    "website": "https://getupsoft.com",
    "version": "20.0.1.1.0",
    "countries": ["do"],
    "depends": [
        "hr",
        "l10n_do_accounting",
    ],
    "data": [
        "security/ir.access.csv",
        "data/l10n_do_payroll_data.xml",
        "views/hr_employee_views.xml",
        "views/hr_payslip_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}