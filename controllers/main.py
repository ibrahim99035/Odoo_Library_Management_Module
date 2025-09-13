from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError
import json
import base64
from datetime import datetime, date
import logging

_logger = logging.getLogger(__name__)

class LibraryMainController(http.Controller):
    """Main controller for Library Management System"""
    
    def _get_library_config(self):
        """Get library configuration"""
        return request.env['library.config'].sudo().get_config()
    
    def _check_librarian_access(self):
        """Check if current user has librarian access"""
        if not request.env.user.has_group('library_management.group_library_librarian'):
            raise AccessError("Librarian access required")
    
    # =============================================================================
    # DASHBOARD AND HOME
    # =============================================================================
    
    @http.route('/library', type='http', auth='user', website=True)
    def library_home(self, **kw):
        """Library management home page"""
        try:
            config = self._get_library_config()
            
            # Get dashboard statistics
            books_count = request.env['library.book'].search_count([])
            members_count = request.env['library.member'].search_count([])
            active_borrowings = request.env['library.borrowing'].search_count([('state', '=', 'borrowed')])
            overdue_books = request.env['library.borrowing'].search_count([('state', '=', 'overdue')])
            
            # Get recent activities
            recent_borrowings = request.env['library.borrowing'].search([], limit=5, order='borrow_date desc')
            recent_returns = request.env['library.borrowing'].search(
                [('state', '=', 'returned'), ('return_date', '!=', False)], 
                limit=5, 
                order='return_date desc'
            )
            
            # Popular books
            popular_books = request.env['library.book'].search([], limit=10, order='popularity_score desc')
            
            values = {
                'config': config,
                'books_count': books_count,
                'members_count': members_count,
                'active_borrowings': active_borrowings,
                'overdue_books': overdue_books,
                'recent_borrowings': recent_borrowings,
                'recent_returns': recent_returns,
                'popular_books': popular_books,
                'is_librarian': request.env.user.has_group('library_management.group_library_librarian'),
            }
            
            return request.render('library_management.library_home', values)
            
        except Exception as e:
            _logger.error("Library Home Error: %s", str(e))
            return request.render('library_management.error_page', {
                'error': 'Unable to load library dashboard',
                'details': str(e)
            })
    
    # =============================================================================
    # BOOK CATALOG
    # =============================================================================
    
    @http.route('/library/catalog', type='http', auth='user', website=True)
    def book_catalog(self, **kw):
        """Public book catalog"""
        try:
            # Parse search parameters
            search_term = kw.get('search', '')
            category_id = kw.get('category_id')
            author_id = kw.get('author_id')
            available_only = kw.get('available_only', False)
            sort_by = kw.get('sort_by', 'name')
            page = int(kw.get('page', 1))
            per_page = 20
            
            # Build search domain
            domain = [('active', '=', True)]
            if search_term:
                domain.append(['name', 'ilike', search_term])
            if category_id:
                domain.append(['category_id', '=', int(category_id)])
            if author_id:
                domain.append(['author_ids', 'in', [int(author_id)]])
            if available_only:
                domain.extend([['available_copies', '>', 0], ['state', '=', 'available']])
            
            # Set ordering
            order = 'name'
            if sort_by == 'popularity':
                order = 'popularity_score desc'
            elif sort_by == 'rating':
                order = 'average_rating desc'
            elif sort_by == 'newest':
                order = 'create_date desc'
            
            # Search books with pagination
            offset = (page - 1) * per_page
            books = request.env['library.book'].search(domain, limit=per_page, offset=offset, order=order)
            total_books = request.env['library.book'].search_count(domain)
            
            # Get filter options
            categories = request.env['library.category'].search([('active', '=', True)], order='complete_name')
            authors = request.env['library.author'].search([('active', '=', True)], order='name')
            
            # Pagination
            total_pages = (total_books + per_page - 1) // per_page
            
            values = {
                'books': books,
                'categories': categories,
                'authors': authors,
                'search_term': search_term,
                'category_id': int(category_id) if category_id else None,
                'author_id': int(author_id) if author_id else None,
                'available_only': available_only,
                'sort_by': sort_by,
                'current_page': page,
                'total_pages': total_pages,
                'total_books': total_books,
                'has_prev': page > 1,
                'has_next': page < total_pages,
                'prev_page': page - 1 if page > 1 else None,
                'next_page': page + 1 if page < total_pages else None,
            }
            
            return request.render('library_management.book_catalog', values)
            
        except Exception as e:
            _logger.error("Book Catalog Error: %s", str(e))
            return request.render('library_management.error_page', {
                'error': 'Unable to load book catalog',
                'details': str(e)
            })
    
    @http.route('/library/book/<int:book_id>', type='http', auth='user', website=True)
    def book_detail(self, book_id, **kw):
        """Book detail page"""
        try:
            book = request.env['library.book'].browse(book_id)
            if not book.exists():
                return request.not_found()
            
            # Get related books (same category or author)
            related_books = request.env['library.book'].search([
                '|', ('category_id', '=', book.category_id.id),
                ('author_ids', 'in', book.author_ids.ids),
                ('id', '!=', book.id)
            ], limit=6)
            
            # Check if current user can make reservations
            can_reserve = False
            current_member = None
            if request.env.user.library_member_id:
                current_member = request.env.user.library_member_id
                can_borrow, _ = current_member.can_borrow_book()
                can_reserve = can_borrow and book.available_copies == 0
            
            values = {
                'book': book,
                'related_books': related_books,
                'can_reserve': can_reserve,
                'current_member': current_member,
                'is_librarian': request.env.user.has_group('library_management.group_library_librarian'),
            }
            
            return request.render('library_management.book_detail', values)
            
        except Exception as e:
            _logger.error("Book Detail Error: %s", str(e))
            return request.render('library_management.error_page', {
                'error': 'Unable to load book details',
                'details': str(e)
            })
    
    # =============================================================================
    # BOOK RESERVATIONS
    # =============================================================================
    
    @http.route('/library/book/<int:book_id>/reserve', type='http', auth='user', methods=['POST'], csrf=True)
    def reserve_book(self, book_id, **post):
        """Reserve a book"""
        try:
            book = request.env['library.book'].browse(book_id)
            if not book.exists():
                return request.not_found()
            
            member = request.env.user.library_member_id
            if not member:
                return request.redirect('/library/member/register?return_url=/library/book/%d' % book_id)
            
            # Check if member can reserve
            can_borrow, message = member.can_borrow_book()
            if not can_borrow:
                request.session['error_message'] = f"Cannot reserve book: {message}"
                return request.redirect('/library/book/%d' % book_id)
            
            # Check if book needs reservation
            if book.available_copies > 0:
                request.session['error_message'] = "Book is available for immediate borrowing"
                return request.redirect('/library/book/%d' % book_id)
            
            # Check if already reserved
            existing_reservation = request.env['library.reservation'].search([
                ('member_id', '=', member.id),
                ('book_id', '=', book.id),
                ('state', '=', 'active')
            ])
            if existing_reservation:
                request.session['error_message'] = "You have already reserved this book"
                return request.redirect('/library/book/%d' % book_id)
            
            # Create reservation
            reservation = request.env['library.reservation'].create({
                'member_id': member.id,
                'book_id': book.id,
                'notes': post.get('notes', '')
            })
            
            request.session['success_message'] = f"Book reserved successfully. Your queue position: {reservation.queue_position}"
            return request.redirect('/library/book/%d' % book_id)
            
        except Exception as e:
            _logger.error("Reserve Book Error: %s", str(e))
            request.session['error_message'] = "Unable to reserve book. Please try again."
            return request.redirect('/library/book/%d' % book_id)
    
    # =============================================================================
    # MEMBER REGISTRATION
    # =============================================================================
    
    @http.route('/library/member/register', type='http', auth='user', website=True)
    def member_register_form(self, **kw):
        """Member registration form"""
        try:
            # Check if user already has a library member account
            if request.env.user.library_member_id:
                return request.redirect('/library/member/profile')
            
            # Get countries for dropdown
            countries = request.env['res.country'].search([], order='name')
            
            values = {
                'countries': countries,
                'return_url': kw.get('return_url', '/library'),
                'membership_types': [
                    ('student', 'Student'),
                    ('faculty', 'Faculty'),
                    ('staff', 'Staff'),
                    ('public', 'Public'),
                    ('senior', 'Senior Citizen'),
                ]
            }
            
            return request.render('library_management.member_register_form', values)
            
        except Exception as e:
            _logger.error("Member Register Form Error: %s", str(e))
            return request.render('library_management.error_page', {
                'error': 'Unable to load registration form',
                'details': str(e)
            })
    
    @http.route('/library/member/register', type='http', auth='user', methods=['POST'], csrf=True)
    def member_register_submit(self, **post):
        """Process member registration"""
        try:
            # Check if user already has a library member account
            if request.env.user.library_member_id:
                return request.redirect('/library/member/profile')
            
            # Validate required fields
            required_fields = ['name', 'email', 'membership_type']
            missing_fields = [field for field in required_fields if not post.get(field)]
            if missing_fields:
                request.session['error_message'] = f"Missing required fields: {', '.join(missing_fields)}"
                return request.redirect('/library/member/register')
            
            # Create library member
            member_vals = {
                'name': post['name'],
                'email': post['email'],
                'phone': post.get('phone', ''),
                'mobile': post.get('mobile', ''),
                'address': post.get('address', ''),
                'city': post.get('city', ''),
                'state': post.get('state', ''),
                'zip_code': post.get('zip_code', ''),
                'country_id': int(post['country_id']) if post.get('country_id') else False,
                'membership_type': post['membership_type'],
                'birth_date': post.get('birth_date') if post.get('birth_date') else False,
                'gender': post.get('gender', ''),
                'student_id': post.get('student_id', ''),
                'employee_id': post.get('employee_id', ''),
                'department': post.get('department', ''),
                'institution': post.get('institution', ''),
                'emergency_contact_name': post.get('emergency_contact_name', ''),
                'emergency_contact_phone': post.get('emergency_contact_phone', ''),
                'user_id': request.env.user.id,
                'partner_id': request.env.user.partner_id.id,
            }
            
            member = request.env['library.member'].create(member_vals)
            
            # Link user to member
            request.env.user.library_member_id = member.id
            
            request.session['success_message'] = f"Registration successful! Your member ID is: {member.member_id}"
            
            # Redirect to return URL or profile
            return_url = post.get('return_url', '/library/member/profile')
            return request.redirect(return_url)
            
        except Exception as e:
            _logger.error("Member Register Submit Error: %s", str(e))
            request.session['error_message'] = "Registration failed. Please try again."
            return request.redirect('/library/member/register')
    
    # =============================================================================
    # QUICK ACTIONS FOR LIBRARIANS
    # =============================================================================
    
    @http.route('/library/quick-borrow', type='http', auth='user', website=True)
    def quick_borrow_form(self, **kw):
        """Quick book borrowing form for librarians"""
        try:
            self._check_librarian_access()
            
            values = {
                'member_id': kw.get('member_id', ''),
                'book_id': kw.get('book_id', ''),
            }
            
            return request.render('library_management.quick_borrow_form', values)
            
        except AccessError:
            return request.redirect('/library')
        except Exception as e:
            _logger.error("Quick Borrow Form Error: %s", str(e))
            return request.render('library_management.error_page', {
                'error': 'Unable to load quick borrow form',
                'details': str(e)
            })
    
    @http.route('/library/quick-borrow', type='http', auth='user', methods=['POST'], csrf=True)
    def quick_borrow_submit(self, **post):
        """Process quick book borrowing"""
        try:
            self._check_librarian_access()
            
            member_query = post.get('member_query', '').strip()
            book_query = post.get('book_query', '').strip()
            
            if not member_query or not book_query:
                request.session['error_message'] = "Member and book information required"
                return request.redirect('/library/quick-borrow')
            
            # Find member
            member = None
            # Try by member ID first
            if member_query.isdigit() or member_query.startswith('M'):
                member = request.env['library.member'].search([('member_id', '=', member_query)], limit=1)
            # Try by email
            if not member:
                member = request.env['library.member'].search([('email', '=', member_query)], limit=1)
            # Try by name
            if not member:
                member = request.env['library.member'].search([('name', 'ilike', member_query)], limit=1)
            
            if not member:
                request.session['error_message'] = f"Member not found: {member_query}"
                return request.redirect('/library/quick-borrow')
            
            # Find book
            book = None
            # Try by ISBN
            book = request.env['library.book'].search([('isbn', '=', book_query)], limit=1)
            # Try by barcode
            if not book:
                book = request.env['library.book'].search([('barcode', '=', book_query)], limit=1)
            # Try by name
            if not book:
                book = request.env['library.book'].search([('name', 'ilike', book_query)], limit=1)
            
            if not book:
                request.session['error_message'] = f"Book not found: {book_query}"
                return request.redirect('/library/quick-borrow')
            
            # Check if member can borrow
            can_borrow, message = member.can_borrow_book()
            if not can_borrow:
                request.session['error_message'] = f"Cannot borrow: {message}"
                return request.redirect('/library/quick-borrow')
            
            # Check book availability
            if not book.check_availability():
                request.session['error_message'] = f"Book not available: {book.name}"
                return request.redirect('/library/quick-borrow')
            
            # Create borrowing
            borrowing = request.env['library.borrowing'].create({
                'member_id': member.id,
                'book_id': book.id,
                'book_condition_borrow': post.get('book_condition_borrow', 'good'),
                'notes': post.get('notes', '')
            })
            
            request.session['success_message'] = f"Book borrowed successfully: {book.name} to {member.name}"
            return request.redirect('/library/quick-borrow')
            
        except AccessError:
            return request.redirect('/library')
        except Exception as e:
            _logger.error("Quick Borrow Submit Error: %s", str(e))
            request.session['error_message'] = "Borrowing failed. Please try again."
            return request.redirect('/library/quick-borrow')
    
    @http.route('/library/quick-return', type='http', auth='user', website=True)
    def quick_return_form(self, **kw):
        """Quick book return form for librarians"""
        try:
            self._check_librarian_access()
            
            values = {
                'borrowing_id': kw.get('borrowing_id', ''),
            }
            
            return request.render('library_management.quick_return_form', values)
            
        except AccessError:
            return request.redirect('/library')
        except Exception as e:
            _logger.error("Quick Return Form Error: %s", str(e))
            return request.render('library_management.error_page', {
                'error': 'Unable to load quick return form',
                'details': str(e)
            })
    
    @http.route('/library/quick-return', type='http', auth='user', methods=['POST'], csrf=True)
    def quick_return_submit(self, **post):
        """Process quick book return"""
        try:
            self._check_librarian_access()
            
            query = post.get('query', '').strip()
            if not query:
                request.session['error_message'] = "Please provide book or member information"
                return request.redirect('/library/quick-return')
            
            # Find active borrowing
            borrowing = None
            
            # Try to find by borrowing ID
            if query.isdigit():
                borrowing = request.env['library.borrowing'].search([
                    ('id', '=', int(query)),
                    ('state', 'in', ['borrowed', 'overdue'])
                ], limit=1)
            
            # Try to find by book ISBN or name
            if not borrowing:
                book = request.env['library.book'].search(['|', ('isbn', '=', query), ('name', 'ilike', query)], limit=1)
                if book:
                    borrowing = request.env['library.borrowing'].search([
                        ('book_id', '=', book.id),
                        ('state', 'in', ['borrowed', 'overdue'])
                    ], limit=1)
            
            # Try to find by member
            if not borrowing:
                member = request.env['library.member'].search(['|', ('member_id', '=', query), ('name', 'ilike', query)], limit=1)
                if member:
                    borrowings = request.env['library.borrowing'].search([
                        ('member_id', '=', member.id),
                        ('state', 'in', ['borrowed', 'overdue'])
                    ])
                    if len(borrowings) == 1:
                        borrowing = borrowings
                    elif len(borrowings) > 1:
                        request.session['error_message'] = f"Multiple books borrowed by {member.name}. Please be more specific."
                        return request.redirect('/library/quick-return')
            
            if not borrowing:
                request.session['error_message'] = f"No active borrowing found for: {query}"
                return request.redirect('/library/quick-return')
            
            # Update borrowing with return details
            borrowing.book_condition_return = post.get('book_condition_return', 'good')
            if post.get('notes'):
                borrowing.notes = (borrowing.notes or '') + f"\nReturn notes: {post['notes']}"
            
            # Return the book
            borrowing.action_return()
            
            request.session['success_message'] = f"Book returned: {borrowing.book_id.name} from {borrowing.member_id.name}"
            return request.redirect('/library/quick-return')
            
        except AccessError:
            return request.redirect('/library')
        except Exception as e:
            _logger.error("Quick Return Submit Error: %s", str(e))
            request.session['error_message'] = "Return failed. Please try again."
            return request.redirect('/library/quick-return')
    
    # =============================================================================
    # AJAX ENDPOINTS FOR AUTOCOMPLETE
    # =============================================================================
    
    @http.route('/library/ajax/search-members', type='json', auth='user')
    def ajax_search_members(self, term):
        """AJAX endpoint to search members for autocomplete"""
        try:
            self._check_librarian_access()
            
            members = request.env['library.member'].search([
                '|', '|', ('name', 'ilike', term),
                ('member_id', 'ilike', term),
                ('email', 'ilike', term)
            ], limit=10)
            
            return [{
                'id': m.id,
                'member_id': m.member_id,
                'name': m.name,
                'email': m.email,
                'label': f"{m.member_id} - {m.name} ({m.email})"
            } for m in members]
            
        except Exception as e:
            _logger.error("AJAX Search Members Error: %s", str(e))
            return []
    
    @http.route('/library/ajax/search-books', type='json', auth='user')
    def ajax_search_books(self, term):
        """AJAX endpoint to search books for autocomplete"""
        try:
            books = request.env['library.book'].search([
                '|', '|', ('name', 'ilike', term),
                ('isbn', 'ilike', term),
                ('barcode', 'ilike', term)
            ], limit=10)
            
            return [{
                'id': b.id,
                'name': b.name,
                'isbn': b.isbn,
                'authors': ', '.join(b.author_ids.mapped('name')),
                'available': b.available_copies,
                'label': f"{b.isbn} - {b.name} (Available: {b.available_copies})"
            } for b in books]
            
        except Exception as e:
            _logger.error("AJAX Search Books Error: %s", str(e))
            return []
    
    @http.route('/library/ajax/book-availability/<int:book_id>', type='json', auth='user')
    def ajax_book_availability(self, book_id):
        """Get real-time book availability"""
        try:
            book = request.env['library.book'].browse(book_id)
            if not book.exists():
                return {'error': 'Book not found'}
            
            return {
                'available_copies': book.available_copies,
                'total_copies': book.total_copies,
                'borrowed_copies': book.borrowed_copies,
                'is_available': book.check_availability(),
                'reservations_count': len(book.reservation_ids.filtered(lambda r: r.state == 'active'))
            }
            
        except Exception as e:
            _logger.error("AJAX Book Availability Error: %s", str(e))
            return {'error': 'Unable to check availability'}
    
    # =============================================================================
    # REPORTS AND EXPORTS
    # =============================================================================
    
    @http.route('/library/reports', type='http', auth='user', website=True)
    def reports_dashboard(self, **kw):
        """Reports and analytics dashboard"""
        try:
            self._check_librarian_access()
            
            # Basic statistics
            stats = {
                'total_books': request.env['library.book'].search_count([]),
                'total_members': request.env['library.member'].search_count([]),
                'active_borrowings': request.env['library.borrowing'].search_count([('state', '=', 'borrowed')]),
                'overdue_books': request.env['library.borrowing'].search_count([('state', '=', 'overdue')]),
                'total_fines_pending': sum(request.env['library.fine'].search([('state', '=', 'pending')]).mapped('amount')),
                'books_added_this_month': request.env['library.book'].search_count([
                    ('create_date', '>=', datetime.now().replace(day=1).strftime('%Y-%m-%d'))
                ]),
            }
            
            # Most borrowed books
            most_borrowed = request.env['library.book'].search([], limit=10, order='popularity_score desc')
            
            # Most active members
            most_active_members = request.env['library.member'].search([], limit=10, order='total_borrowed desc')
            
            # Overdue borrowings
            overdue_borrowings = request.env['library.borrowing'].search([('state', '=', 'overdue')], limit=20)
            
            values = {
                'stats': stats,
                'most_borrowed': most_borrowed,
                'most_active_members': most_active_members,
                'overdue_borrowings': overdue_borrowings,
            }
            
            return request.render('library_management.reports_dashboard', values)
            
        except AccessError:
            return request.redirect('/library')
        except Exception as e:
            _logger.error("Reports Dashboard Error: %s", str(e))
            return request.render('library_management.error_page', {
                'error': 'Unable to load reports dashboard',
                'details': str(e)
            })
    
    @http.route('/library/export/overdue', type='http', auth='user')
    def export_overdue_books(self, **kw):
        """Export overdue books to CSV"""
        try:
            self._check_librarian_access()
            
            overdue_borrowings = request.env['library.borrowing'].search([('state', '=', 'overdue')])
            
            # Generate CSV content
            import io
            import csv
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Headers
            writer.writerow([
                'Member ID', 'Member Name', 'Member Email', 'Book Title', 'ISBN',
                'Borrow Date', 'Due Date', 'Days Overdue', 'Fine Amount'
            ])
            
            # Data rows
            for borrowing in overdue_borrowings:
                writer.writerow([
                    borrowing.member_id.member_id,
                    borrowing.member_id.name,
                    borrowing.member_id.email,
                    borrowing.book_id.name,
                    borrowing.book_id.isbn,
                    borrowing.borrow_date.strftime('%Y-%m-%d') if borrowing.borrow_date else '',
                    borrowing.due_date.strftime('%Y-%m-%d') if borrowing.due_date else '',
                    borrowing.days_overdue,
                    borrowing.fine_amount,
                ])
            
            output.seek(0)
            content = output.getvalue()
            output.close()
            
            # Return CSV file
            filename = f"overdue_books_{date.today().strftime('%Y%m%d')}.csv"
            return request.make_response(
                content,
                headers=[
                    ('Content-Type', 'text/csv'),
                    ('Content-Disposition', f'attachment; filename="{filename}"')
                ]
            )
            
        except AccessError:
            return request.redirect('/library')
        except Exception as e:
            _logger.error("Export Overdue Books Error: %s", str(e))
            return request.make_response("Export failed", status=500)