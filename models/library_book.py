from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
import re

class LibraryBook(models.Model):
    _name = 'library.book'
    _description = 'Library Book'
    _order = 'name'
    _rec_name = 'name'

    # Inherit mail features for chatter functionality
    # Chatter is a built-in Odoo feature for logging messages and tracking changes
    # tracking = True, indicates that changes to this field should be tracked in the chatter
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Title', required=True, tracking=True)

    # ISBN is a unique identifier for books
    isbn = fields.Char('ISBN', required=True, tracking=True)
    isbn13 = fields.Char('ISBN-13')
    
    # Many2many relationship to authors
    # Book is able to relate to multiple authors and each author can write multiple books
    # Target Model is 'library.author' - 'library_book_author_rel' is the relation table
    # 'book_id' is the column in the relation table that points to this model
    # 'author_id' is the column in the relation table that points to the target model
    author_ids = fields.Many2many('library.author', 'library_book_author_rel', 'book_id', 'author_id', 'Authors', required=True)
    
    # Many2one relationship to publisher
    # Each book has one publisher, but a publisher can publish multiple books
    # Target Model is 'library.publisher' - 'publisher_id' is the foreign key in this model
    publisher_id = fields.Many2one('library.publisher', 'Publisher', tracking=True)

    # Many2one relationship to category
    # Each book belongs to one category, but a category can have multiple books
    # Target Model is 'library.category' - 'category_id' is the foreign key in this model
    category_id = fields.Many2one('library.category', 'Category', required=True, tracking=True)
    
    publication_date = fields.Date('Publication Date')
    
    pages = fields.Integer('Pages')
    
    # Book language with selection options
    language = fields.Selection([
        ('en', 'English'),
        ('ar', 'Arabic'),
        ('fr', 'French'),
        ('es', 'Spanish'),
        ('de', 'German'),
        ('it', 'Italian'),
        ('pt', 'Portuguese'),
        ('ru', 'Russian'),
        ('ja', 'Japanese'),
        ('zh', 'Chinese'),
    ], 'Language', default='en')

    edition = fields.Char('Edition')
    
    description = fields.Html('Description')
    cover_image = fields.Binary('Cover Image')
    
    total_copies = fields.Integer('Total Copies', default=1, required=True, tracking=True)
    available_copies = fields.Integer('Available Copies', compute='_compute_available_copies', store=True)
    borrowed_copies = fields.Integer('Borrowed Copies', compute='_compute_borrowed_copies')
    
    location = fields.Char('Shelf Location', tracking=True)
    
    barcode = fields.Char('Barcode')
    price = fields.Float('Price', digits='Product Price')
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
    
    state = fields.Selection([
        ('available', 'Available'),
        ('maintenance', 'Maintenance'),
        ('lost', 'Lost'),
        ('damaged', 'Damaged'),
    ], 'Status', default='available', tracking=True)
    
    # One2many relationships to other models as 'library.borrowing', 'library.reservation', 'library.review'
    # 'book_id' is the foreign key in the related models that points back to this model
    borrowing_ids = fields.One2many('library.borrowing', 'book_id', 'Borrowing History')
    reservation_ids = fields.One2many('library.reservation', 'book_id', 'Reservations')
    review_ids = fields.One2many('library.review', 'book_id', 'Reviews')
    
    # Computed fields for ratings and popularity
    average_rating = fields.Float('Average Rating', compute='_compute_average_rating', store=True)
    review_count = fields.Integer('Review Count', compute='_compute_review_count', store=True)
    popularity_score = fields.Float('Popularity Score', compute='_compute_popularity_score', store=True)
    
    acquisition_date = fields.Date('Acquisition Date', default=fields.Date.today)
    
    cost = fields.Float('Cost', digits='Product Price')
    supplier = fields.Char('Supplier')
    
    notes = fields.Text('Notes')
    tags = fields.Char('Tags')
    
    active = fields.Boolean('Active', default=True)
    
    subject = fields.Char('Subject')
    keywords = fields.Char('Keywords')
    dewey_decimal = fields.Char('Dewey Decimal Classification')
    
    # SQL constraints to enforce data integrity for ISBN uniqueness and positive total copies
    _sql_constraints = [
        ('isbn_unique', 'UNIQUE(isbn)', 'ISBN must be unique!'),
        ('total_copies_positive', 'CHECK(total_copies > 0)', 'Total copies must be positive!'),
    ]

    # Compute method to calculate available copies
    # It counts the number of borrowed copies and subtracts from total copies
    @api.depends('borrowing_ids', 'borrowing_ids.state', 'total_copies') # Dependencies triggers for recomputation
    def _compute_available_copies(self):
        for book in self:
            borrowed = len(book.borrowing_ids.filtered(lambda b: b.state == 'borrowed'))
            book.available_copies = book.total_copies - borrowed

    # Compute method to calculate borrowed copies
    # It counts the number of currently borrowed copies 
    @api.depends('borrowing_ids', 'borrowing_ids.state') # Dependencies triggers for recomputation
    def _compute_borrowed_copies(self):
        for book in self:
            book.borrowed_copies = len(book.borrowing_ids.filtered(lambda b: b.state == 'borrowed'))

    # Compute method to calculate average rating from related reviews
    @api.depends('review_ids.rating')
    def _compute_average_rating(self):
        for book in self:
            if book.review_ids:
                ratings = book.review_ids.mapped('rating')
                book.average_rating = sum(ratings) / len(ratings)
            else:
                book.average_rating = 0.0

    # Compute method to count the number of reviews
    @api.depends('review_ids')
    def _compute_review_count(self):
        for book in self:
            book.review_count = len(book.review_ids)

    # Compute method to calculate a popularity score based on borrowings, reviews, and average rating
    @api.depends('borrowing_ids', 'review_ids', 'average_rating')
    def _compute_popularity_score(self):
        for book in self:
            borrow_count = len(book.borrowing_ids)
            review_count = len(book.review_ids)
            rating = book.average_rating
            book.popularity_score = (borrow_count * 0.5) + (review_count * 0.3) + (rating * 0.2)

    # Constraint to validate ISBN format
    # It uses helper methods to validate ISBN-10 and ISBN-13 formats
    @api.constrains('isbn')
    def _check_isbn(self):
        for book in self:
            if book.isbn and not self._validate_isbn(book.isbn):
                raise ValidationError('Invalid ISBN format!')

    # Helper methods for ISBN validation - handles both ISBN-10 and ISBN-13 formats
    def _validate_isbn(self, isbn):
        isbn = re.sub(r'[^0-9X]', '', isbn.upper())
        if len(isbn) == 10:
            return self._validate_isbn10(isbn)
        elif len(isbn) == 13:
            return self._validate_isbn13(isbn)
        return False

    # Helper method to validate ISBN-10 format - checksum calculation
    def _validate_isbn10(self, isbn):
        if len(isbn) != 10:
            return False
        check = 0
        for i in range(9):
            check += int(isbn[i]) * (10 - i)
        check = (11 - (check % 11)) % 11
        return str(check) == isbn[9] or (check == 10 and isbn[9] == 'X')

    # Helper method to validate ISBN-13 format - checksum calculation
    def _validate_isbn13(self, isbn):
        if len(isbn) != 13:
            return False
        check = sum(int(isbn[i]) * (1 if i % 2 == 0 else 3) for i in range(12))
        return int(isbn[12]) == (10 - (check % 10)) % 10

    # Onchange method to ensure total copies is not set below borrowed copies
    @api.onchange('total_copies')
    def _onchange_total_copies(self):
        if self.total_copies < self.borrowed_copies:
            raise UserError('Total copies cannot be less than borrowed copies!')

    # Action methods to change book state - maintenance, available, lost, damaged
    def action_set_maintenance(self):
        self.state = 'maintenance'

    def action_set_available(self):
        self.state = 'available'

    def action_set_lost(self):
        self.state = 'lost'

    def action_set_damaged(self):
        self.state = 'damaged'

    def check_availability(self):
        return self.available_copies > 0 and self.state == 'available'