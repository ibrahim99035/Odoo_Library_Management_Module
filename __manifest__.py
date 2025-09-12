{
    'name': 'Knowledge Shelfs Hive',
    'version': '18.0.1.0.0',
    'category': 'Library',
    'summary':'Complete Library Management System',
    'description': """
        Advanced Library Management System
        ===================================
        * Book catalog management
        * Member registration and management
        * Borrowing and return tracking
        * Fine management system
        * Reservation system
        * Reports and analytics
        * Web portal for members
        * Barcode integration
        * Email notifications
    """,
    'author': 'Ibrahim Mohamed Eita',
    'website': 'https://solid-portfolio-bice.vercel.app',
    'depends': [
        'base',
        'mail',
        'portal',
        'website',
        'web',
        'report_xlsx',
        'web_kanban_gauge',
        'web_dashboard_tile',
    ],
    'data': [
        # Security
        'security/library_groups.xml',
        'security/library_security.xml',
        'security/ir.model.access.csv',
        
        # Data
        'data/library_sequence_data.xml',
        'data/library_category_data.xml',
        'data/library_config_data.xml',
        'data/mail_template_data.xml',
        'data/cron_data.xml',
        
        # Views
        'views/library_config_views.xml',
        'views/library_category_views.xml',
        'views/library_author_views.xml',
        'views/library_publisher_views.xml',
        'views/library_book_views.xml',
        'views/library_member_views.xml',
        'views/library_borrowing_views.xml',
        'views/library_fine_views.xml',
        'views/library_reservation_views.xml',
        'views/library_review_views.xml',
        'views/library_dashboard_views.xml',
        'views/library_actions.xml',
        'views/library_menu.xml',
        'views/portal_templates.xml',
        
        # Wizards
        'wizard/book_import_wizard_views.xml',
        'wizard/fine_payment_wizard_views.xml',
        'wizard/membership_renewal_wizard_views.xml',
        'wizard/book_transfer_wizard_views.xml',
        
        # Reports
        'reports/report_views.xml',
        'reports/book_catalog_template.xml',
        'reports/member_card_template.xml',
        'reports/overdue_books_template.xml',
        'reports/fine_statement_template.xml',
        'reports/monthly_activity_template.xml',
        'reports/inventory_template.xml',
    ],
    'demo': [
        'data/demo_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'library_management/static/src/css/library_style.css',
            'library_management/static/src/css/dashboard_style.css',
            'library_management/static/src/js/library_dashboard.js',
            'library_management/static/src/js/library_widgets.js',
            'library_management/static/src/js/barcode_scanner.js',
        ],
        'web.assets_frontend': [
            'library_management/static/src/css/portal_style.css',
            'library_management/static/src/js/library_portal.js',
            'library_management/static/src/js/book_search.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
    'sequence': 10,
}