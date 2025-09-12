from odoo import models, fields, api

class LibraryConfig(models.Model):
    _name = 'library.config' # Technical Name of the model - library_config in the database
    _description = 'Library Configuration' # Description of the model
    _rec_name = 'library_name' # refers to the first field, its value would be used in dropdowns and search

    # The main name of the library - required field - _rec_name refrence 
    library_name = fields.Char(string='Library Name', required=True)

    # Contact Information
    address = fields.Text(string='Address')
    phone = fields.Char(string='Phone Number')
    email = fields.Char(string='Email')
    website = fields.Char(string='Website')

    # Borrowing Policies - default values provided - Integer and Float fields
    max_borrow_days = fields.Integer(string='Max Borrow Days', default=14)
    max_renewals = fields.Integer(string='Max Renewals', default=2)
    fine_per_day = fields.Float(string='Fine Per Day', default=1.0)

    # Borrowing Limits - default values provided - Integer fields for different user types
    max_books_student = fields.Integer(string='Max Books per Student', default=5)
    max_books_faculty = fields.Integer(string='Max Books per Faculty', default=10)
    max_books_public = fields.Integer(string='Max Books per Public', default=3)

    # Notification Settings - default values provided - Integer fields
    reservation_expiry_days = fields.Integer(string='Reservation Expiry Days', default=7)
    overdue_notification_days = fields.Integer(string='Overdue Notification Days', default=3)
    
    # Working Hours and Status - Float fields for hours
    working_hours_start = fields.Float(string='Working Hours Start', default=8.0)
    working_hours_end = fields.Float(string='Working Hours End', default=20.0)

    # Status field to activate/deactivate - Boolean field - Active by default
    isActive = fields.Boolean(string='Is Active', default=True)

    # Ensures that thres is always one config record, If none exists, create one with default values
    @api.model
    def get_config(self):
        config = self.search([], limit=1)
        if not config:
            config = self.create({'library_name': 'Default Library'})
        return config