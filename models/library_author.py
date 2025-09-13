from odoo import models, fields, api
from datetime import date
from odoo.exceptions import ValidationError
import re

class LibraryAuthor(models.Model):
    _name = 'library.author'
    _description = 'Book Author'
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char(string='Author Name', required=True)
    biography = fields.Html(string = 'Biography') # rich html content stored as text in the database
    
    birth_date = fields.Date(string= 'Birth Date') 
    death_date = fields.Date(string= 'Death Date')
    nationality = fields.Char(string = 'Nationality')
    
    # Many-to-Many relationship with library.book model - through an intermediary table - library_book_author_rel
    # An author can write multiple books and a book can have multiple authors
    # 'library.book' is the target model
    # 'library_book_author_rel' is the name of the intermediary table
    # 'author_id' is the column in the intermediary table that refers to this model (library.author)
    # 'book_id' is the column in the intermediary table that refers to the target model (library.book)
    book_ids = fields.Many2many('library.book', 'library_book_author_rel', 'author_id', 'book_id', string='Books')
    
    # Computed fields
    book_count = fields.Integer('Number of Books', compute='_compute_book_count', store=True)
    average_rating = fields.Float('Average Rating', compute='_compute_average_rating')
    
    website = fields.Char('Website')
    email = fields.Char('Email')
    awards = fields.Text('Awards & Recognition')
    
    active = fields.Boolean('Active', default=True)
    
    age = fields.Integer('Age', compute='_compute_age')
    is_alive = fields.Boolean('Is Alive', compute='_compute_is_alive')

    # SQL constraint to ensure death_date is after birth_date if death_date is set
    _sql_constraints = [
        ('birth_death_check', 'CHECK(death_date IS NULL OR death_date >= birth_date)', 
         'Death date must be after birth date!')
    ]

    #### Compute Methods ####

    # Computes the number of books written by the author
    @api.depends('book_ids') # Triggered when book_ids changes
    def _compute_book_count(self):
        for author in self: 
            author.book_count = len(author.book_ids)

    # Computes the average rating of all books written by the author
    @api.depends('book_ids.average_rating') # Triggered when average_rating of related books changes
    def _compute_average_rating(self):
        for author in self:
            if author.book_ids:
                ratings = author.book_ids.mapped('average_rating')
                author.average_rating = sum(ratings) / len(ratings) if ratings else 0.0
            else:
                author.average_rating = 0.0

    # Computes the age of the author based on birth_date and death_date (or current date if alive)
    @api.depends('birth_date', 'death_date') # Triggered when birth_date or death_date changes
    def _compute_age(self):
        for author in self:
            if author.birth_date:
                end_date = author.death_date or date.today()
                author.age = (end_date - author.birth_date).days // 365
            else:
                author.age = 0

    # Computes if the author is alive based on death_date
    @api.depends('death_date') # Triggered when death_date changes
    def _compute_is_alive(self):
        for author in self:
            author.is_alive = not author.death_date

    # -----------------------------
    # VALIDATIONS
    # -----------------------------
    @api.constrains('email', 'website')
    def _check_contact_info(self):
        email_pattern = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")
        website_pattern = re.compile(r"^(http|https)://[^\s/$.?#].[^\s]*$")

        for publisher in self:
            # Validate email if filled
            if publisher.email and not email_pattern.match(publisher.email):
                raise ValidationError("Invalid Email format for publisher: %s" % publisher.name)

            # Validate website if filled
            if publisher.website and not website_pattern.match(publisher.website):
                raise ValidationError("Invalid Website URL for publisher: %s. It should start with http:// or https://." % publisher.name)