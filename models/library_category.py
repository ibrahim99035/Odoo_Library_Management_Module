from odoo import models, fields, api
from odoo.exceptions import ValidationError

class LibraryCategory(models.Model):
    _name = 'library.category' # library_categoryin the database
    _description = 'Book Category' # Description of the model
    
    _parent_name = "parent_id" # Indicates that this models is a hirerarchy and parent_id field points to the parent
    _parent_store = True # for efficient searching in hierarchies maintaining the parent_path field
    
    _rec_name = 'complete_name' # display complete_name in dropdowns and search
    _order = 'complete_name' # Default sorting order in lists

    name = fields.Char(string='Category Name', required=True) 

    # Calculated field stored in the database for performance (not calculated everytime)
    complete_name = fields.Char(string='Complete Name', compute='_compute_complete_name', store=True) 
    
    # Many-to-One relationship field - Each category can have one parent category - Self-referential
    # If a parent category is deleted, all its child categories are also deleted (ondelete='cascade')
    parent_id = fields.Many2one('library.category', string='Parent Category', ondelete='cascade')
    
    # Shows the full path of parent categories for efficient searching 
    parent_path = fields.Char(index=True)

    # One-to-Many relation, reverse of parent_id - Each category can have multiple children 
    child_ids = fields.One2many('library.category', 'parent_id', string='Child Categories')
    
    description = fields.Text(string='Description', translate=True)
    
    # One-to-Many relation to another model named library_book
    # Means each category can have multiple books associated with it
    # In reverse side, category_id field must exist in (library.book).
    book_ids = fields.One2many('library.book', 'category_id', string='Books')
    
    # Computed Integer field (number of books) in this category.
    book_count = fields.Integer(string='Book Count', compute='_compute_book_count')
    
    active = fields.Boolean(string='Active', default=True)
    sequence = fields.Integer(string='Sequence', default=10)

    # Prevents having two categories with the same name under the same parent_id
    _sql_constraints = [
        ('name_uniq', 'UNIQUE(name, parent_id)', 'Category name must be unique!'),
    ]

    ####Compute Methods####

    # Computes the number of books in each category
    @api.depends('book_ids') # Triggered when book_ids changes to add to the count
    def _compute_book_count(self): # self is a recordset of several categories
        for category in self: # Iterate through each category in the recordset
            category.book_count = len(category.book_ids) # Count the number of related books

    @api.depends('name', 'parent_id')
    def _compute_complete_name(self): # self is a recordset of several categories
        for category in self: # Iterate through each category in the recordset
            if category.parent_id:  # If there is a parent category
                # get the parent's complete_name and append this category's name
                category.complete_name = f"{category.parent_id.complete_name} / {category.name}" 
            else:
                # No parent, complete_name is just the category's name
                category.complete_name = category.name

    @api.constrains('parent_id') # Triggered when parent_id changes to check for recursion
    def _check_parent_id(self): # self is a recordset of several categories
        for category in self: # Iterate through each category in the recordset
            if not category._check_recursion(): # Built-in method to check for recursive relationships
                # If recursion is detected, raise a validation error
                raise ValidationError('You cannot create recursive categories.') 