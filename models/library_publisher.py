from odoo import models, fields, api
from odoo.exceptions import ValidationError
import re

class LibraryPublisher(models.Model):
    _name = 'library.publisher'
    _description = 'Book Publisher'
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char(string='Publisher Name', required=True)
    address = fields.Text(string='Address')

    city = fields.Char(string='City')
    state = fields.Char(string='State')
    country = fields.Char(string='Country')
    
    website = fields.Char(string='Website')
    contact_person = fields.Char(string='Contact Person')
    phone = fields.Char(string='Phone Number')
    email = fields.Char(string='Email')
    
    # Relation to books published by this publisher
    # Each book will have a Many2one field 'publisher_id' pointing to this model
    book_ids = fields.One2many('library.book', 'publisher_id', string='Books Published')
    
    book_count = fields.Integer(string='Book Count', compute='_compute_book_count')
    
    active = fields.Boolean(string='Active', default=True)
    
    # Publisher logo - an image file stored as binary data - in PostgrSQL stored as bytea - base64 encoded
    logo = fields.Binary(string='Logo')

    @api.depends('book_ids')  # Recompute when book_ids changes
    def _compute_book_count(self):
        for publisher in self:
            publisher.book_count = len(publisher.book_ids)

    # -----------------------------
    # VALIDATIONS
    # -----------------------------
    @api.constrains('email', 'phone', 'website')
    def _check_contact_info(self):
        email_pattern = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")
        phone_pattern = re.compile(r"^\+?\d{7,15}$")  # + optional, 7-15 digits
        website_pattern = re.compile(r"^(http|https)://[^\s/$.?#].[^\s]*$")

        for publisher in self:
            # Validate email if filled
            if publisher.email and not email_pattern.match(publisher.email):
                raise ValidationError("Invalid Email format for publisher: %s" % publisher.name)

            # Validate phone if filled
            if publisher.phone and not phone_pattern.match(publisher.phone):
                raise ValidationError("Invalid Phone Number for publisher: %s. Use digits and optional +." % publisher.name)

            # Validate website if filled
            if publisher.website and not website_pattern.match(publisher.website):
                raise ValidationError("Invalid Website URL for publisher: %s. It should start with http:// or https://." % publisher.name)