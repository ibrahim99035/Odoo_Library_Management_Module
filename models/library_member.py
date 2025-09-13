from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import date, timedelta
import re

class LibraryMember(models.Model):
    _name = 'library.member'
    _description = 'Library Member'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char('Member Name', required=True, tracking=True)

    # Member ID is generated via sequence 'on create' in the create method below
    # required - duplication is not allowed - Readonly after creation 
    # Deafult value uses lambda to call sequence 
    member_id = fields.Char('Member ID', 
        required=True, copy=False, readonly=True,
        # Lambda function is a nameless anonymous function
        # The syntax is lambda arguments: expression
        # Here, it takes self as an argument and calls the sequence to get the next value
        # self.env['ir.sequence'] accesses the ir.sequence model which is a built-in Odoo model for managing sequences
        # next_by_code('library.member') generates the next sequence value for the code 'library.member'
        # The generation is based on the sequence configuration in the Odoo backend 
        default=lambda self: self.env['ir.sequence'].next_by_code('library.member')
    )

    # Member's contact and personal details
    email = fields.Char('Email', required=True, tracking=True)
    phone = fields.Char('Phone', tracking=True)
    mobile = fields.Char('Mobile')
    address = fields.Text('Address')
    city = fields.Char('City')
    state = fields.Char('State')
    zip_code = fields.Char('ZIP Code')
    country_id = fields.Many2one('res.country', 'Country')
    
    # Memeber's demographic details
    birth_date = fields.Date('Birth Date')
    age = fields.Integer('Age', compute='_compute_age')
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], 'Gender')
    
    # Membership details
    join_date = fields.Date('Join Date', default=fields.Date.today, required=True, tracking=True)
    expiry_date = fields.Date('Membership Expiry', compute='_compute_expiry_date', store=True)
    membership_type = fields.Selection([
        ('student', 'Student'),
        ('faculty', 'Faculty'),
        ('staff', 'Staff'),
        ('public', 'Public'),
        ('senior', 'Senior Citizen'),
    ], 'Membership Type', required=True, default='public', tracking=True)
    max_books = fields.Integer('Maximum Books Allowed', compute='_compute_max_books', store=True)
    fine_amount = fields.Float('Outstanding Fines', compute='_compute_fine_amount')
    state = fields.Selection([
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('expired', 'Expired'),
        ('blocked', 'Blocked'),
    ], 'Status', default='active', tracking=True)
    
    # One2many field to 'library.borrowing' model to track borrowings 
    # Member_id is a foreign key in library.borrowing links back to this model
    borrowing_ids = fields.One2many('library.borrowing', 'member_id', 'Borrowing History')

    # Current borrowings - only those with state 'borrowed'
    current_borrowings = fields.One2many('library.borrowing', 'member_id', 'Current Borrowings', 
                                       domain=[('state', '=', 'borrowed')])
    
    # Computed fields for counts
    borrowed_count = fields.Integer('Currently Borrowed', compute='_compute_borrowed_count')
    total_borrowed = fields.Integer('Total Books Borrowed', compute='_compute_total_borrowed')
    
    # Target Model is library.fine - member_id is the foreign key in library.fine linking back to this model
    # This field will show all fines associated with this member 
    fine_ids = fields.One2many('library.fine', 'member_id', 'Fines')
    
    # Target Model is library.reservation - member_id is the foreign key in library.reservation linking back to this model
    # This field will show all reservations associated with this member
    reservation_ids = fields.One2many('library.reservation', 'member_id', 'Reservations')
    
    # Target Model is library.review - member_id is the foreign key in library.review linking back to this model
    # This field will show all reviews associated with this member
    review_ids = fields.One2many('library.review', 'member_id', 'Reviews')
    
     
    photo = fields.Binary('Photo')
    
    notes = fields.Text('Notes')
    
    emergency_contact_name = fields.Char('Emergency Contact Name')
    emergency_contact_phone = fields.Char('Emergency Contact Phone')
    
    student_id = fields.Char('Student ID')
    employee_id = fields.Char('Employee ID')
    department = fields.Char('Department')
    institution = fields.Char('Institution/Organization')
    
    # Portal user and related partner
    user_id = fields.Many2one('res.users', 'Portal User')
    partner_id = fields.Many2one('res.partner', 'Related Partner')
    
    library_card_printed = fields.Boolean('Library Card Printed', default=False)
    card_print_date = fields.Date('Card Print Date')
    
    active = fields.Boolean('Active', default=True)

    # SQL Constraints for data integrity
    #  member_id must be unique
    #  email must be unique
    _sql_constraints = [
        ('member_id_unique', 'UNIQUE(member_id)', 'Member ID must be unique!'),
        ('email_unique', 'UNIQUE(email)', 'Email must be unique!'),
    ]

    # Compute Method for member's age based on birth_date
    @api.depends('birth_date')
    def _compute_age(self):
        for member in self:
            if member.birth_date:
                member.age = (date.today() - member.birth_date).days // 365
            else:
                member.age = 0

    # Compute Method for membership expiry date based on join_date and membership_type
    @api.depends('join_date', 'membership_type')
    def _compute_expiry_date(self):
        for member in self:
            if member.join_date:
                if member.membership_type in ['student', 'faculty', 'staff']:
                    member.expiry_date = member.join_date + timedelta(days=365)
                else:
                    member.expiry_date = member.join_date + timedelta(days=730)  # 2 years for public

    # Compute Method for max_books based on membership_type
    @api.depends('membership_type')
    def _compute_max_books(self):
        config = self.env['library.config'].get_config()
        for member in self:
            if member.membership_type == 'student':
                member.max_books = config.max_books_student
            elif member.membership_type in ['faculty', 'staff']:
                member.max_books = config.max_books_faculty
            else:
                member.max_books = config.max_books_public

    # Compute Method for total outstanding fines
    @api.depends('fine_ids')
    def _compute_fine_amount(self):
        for member in self:
            member.fine_amount = sum(member.fine_ids.filtered(lambda f: f.state == 'pending').mapped('amount'))

    # Compute Method for currently borrowed books count
    @api.depends('current_borrowings')
    def _compute_borrowed_count(self):
        for member in self:
            member.borrowed_count = len(member.current_borrowings)

    # Compute Method for total books borrowed historically
    @api.depends('borrowing_ids')
    def _compute_total_borrowed(self):
        for member in self:
            member.total_borrowed = len(member.borrowing_ids)

    # Check constraints for email format and birth_date validity
    @api.constrains('email')
    def _check_email(self):
        for member in self:
            if member.email and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', member.email):
                raise ValidationError('Invalid email format!')

    # Ensure birth_date is not in the future
    @api.constrains('birth_date')
    def _check_birth_date(self):
        for member in self:
            if member.birth_date and member.birth_date > date.today():
                raise ValidationError('Birth date cannot be in the future!')

    # Business logic to determine if member can borrow a book based on state, borrowed_count, max_books, and outstanding fines
    def can_borrow_book(self):
        if self.state != 'active':
            return False, f"Member is {self.state}"
        if self.borrowed_count >= self.max_books:
            return False, f"Maximum books limit reached ({self.max_books})"
        if self.fine_amount > 0:
            return False, f"Outstanding fines: {self.fine_amount}"
        return True, "Can borrow"

    def action_suspend(self):
        self.state = 'suspended'

    def action_activate(self):
        self.state = 'active'

    def action_block(self):
        self.state = 'blocked'

    def action_print_card(self):
        self.library_card_printed = True
        self.card_print_date = fields.Date.today()
        return self.env.ref('library_management.action_report_member_card').report_action(self)