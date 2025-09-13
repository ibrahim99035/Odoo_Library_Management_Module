from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

class LibraryAPIController(http.Controller):
    """REST API endpoints for Library Management System"""
    
    def _check_api_access(self):
        """Check if user has API access rights"""
        if not request.env.user.has_group('library_management.group_library_user'):
            return {'error': 'Access denied', 'code': 403}
        return None
    
    def _json_response(self, data, status=200):
        """Helper method to return JSON response"""
        response = request.make_response(
            json.dumps(data, default=str, ensure_ascii=False, indent=2),
            headers=[
                ('Content-Type', 'application/json'),
                ('Cache-Control', 'no-cache')
            ]
        )
        response.status_code = status
        return response
    
    # =============================================================================
    # BOOKS API ENDPOINTS
    # =============================================================================
    
    @http.route('/api/books', type='http', auth='user', methods=['GET'], csrf=False)
    def api_books_list(self, **kw):
        """Get list of books with filtering and pagination"""
        access_check = self._check_api_access()
        if access_check:
            return self._json_response(access_check, 403)
        
        try:
            # Parse query parameters
            limit = int(kw.get('limit', 20))
            offset = int(kw.get('offset', 0))
            search = kw.get('search', '')
            category_id = kw.get('category_id')
            author_id = kw.get('author_id')
            available_only = kw.get('available_only', '').lower() == 'true'
            
            # Build domain
            domain = []
            if search:
                domain.append(['name', 'ilike', search])
            if category_id:
                domain.append(['category_id', '=', int(category_id)])
            if author_id:
                domain.append(['author_ids', 'in', [int(author_id)]])
            if available_only:
                domain.extend([['available_copies', '>', 0], ['state', '=', 'available']])
            
            # Get books
            books = request.env['library.book'].search(domain, limit=limit, offset=offset)
            total_count = request.env['library.book'].search_count(domain)
            
            # Format response
            books_data = []
            for book in books:
                books_data.append({
                    'id': book.id,
                    'name': book.name,
                    'isbn': book.isbn,
                    'authors': [{'id': a.id, 'name': a.name} for a in book.author_ids],
                    'category': {'id': book.category_id.id, 'name': book.category_id.name} if book.category_id else None,
                    'publisher': {'id': book.publisher_id.id, 'name': book.publisher_id.name} if book.publisher_id else None,
                    'total_copies': book.total_copies,
                    'available_copies': book.available_copies,
                    'average_rating': book.average_rating,
                    'state': book.state,
                    'location': book.location,
                })
            
            return self._json_response({
                'success': True,
                'data': books_data,
                'pagination': {
                    'total': total_count,
                    'limit': limit,
                    'offset': offset,
                    'has_next': (offset + limit) < total_count
                }
            })
            
        except Exception as e:
            _logger.error("API Books List Error: %s", str(e))
            return self._json_response({'error': 'Internal server error', 'code': 500}, 500)
    
    @http.route('/api/books/<int:book_id>', type='http', auth='user', methods=['GET'], csrf=False)
    def api_book_detail(self, book_id, **kw):
        """Get detailed information about a specific book"""
        access_check = self._check_api_access()
        if access_check:
            return self._json_response(access_check, 403)
        
        try:
            book = request.env['library.book'].browse(book_id)
            if not book.exists():
                return self._json_response({'error': 'Book not found', 'code': 404}, 404)
            
            book_data = {
                'id': book.id,
                'name': book.name,
                'isbn': book.isbn,
                'isbn13': book.isbn13,
                'description': book.description,
                'pages': book.pages,
                'language': book.language,
                'edition': book.edition,
                'publication_date': book.publication_date.isoformat() if book.publication_date else None,
                'authors': [{'id': a.id, 'name': a.name, 'biography': a.biography} for a in book.author_ids],
                'category': {
                    'id': book.category_id.id, 
                    'name': book.category_id.name,
                    'complete_name': book.category_id.complete_name
                } if book.category_id else None,
                'publisher': {
                    'id': book.publisher_id.id, 
                    'name': book.publisher_id.name,
                    'website': book.publisher_id.website
                } if book.publisher_id else None,
                'total_copies': book.total_copies,
                'available_copies': book.available_copies,
                'borrowed_copies': book.borrowed_copies,
                'average_rating': book.average_rating,
                'review_count': book.review_count,
                'popularity_score': book.popularity_score,
                'state': book.state,
                'location': book.location,
                'price': book.price,
                'recent_reviews': [
                    {
                        'id': r.id,
                        'title': r.name,
                        'rating': r.rating,
                        'review_text': r.review_text,
                        'reviewer': r.member_id.name,
                        'review_date': r.review_date.isoformat() if r.review_date else None
                    } for r in book.review_ids.filtered(lambda x: x.state == 'published')[:5]
                ]
            }
            
            return self._json_response({'success': True, 'data': book_data})
            
        except Exception as e:
            _logger.error("API Book Detail Error: %s", str(e))
            return self._json_response({'error': 'Internal server error', 'code': 500}, 500)
    
    # =============================================================================
    # MEMBERS API ENDPOINTS
    # =============================================================================
    
    @http.route('/api/members', type='http', auth='user', methods=['GET'], csrf=False)
    def api_members_list(self, **kw):
        """Get list of library members"""
        access_check = self._check_api_access()
        if access_check:
            return self._json_response(access_check, 403)
        
        # Check if user is librarian
        if not request.env.user.has_group('library_management.group_library_librarian'):
            return self._json_response({'error': 'Librarian access required', 'code': 403}, 403)
        
        try:
            limit = int(kw.get('limit', 20))
            offset = int(kw.get('offset', 0))
            search = kw.get('search', '')
            membership_type = kw.get('membership_type')
            state = kw.get('state')
            
            # Build domain
            domain = []
            if search:
                domain.append(['name', 'ilike', search])
            if membership_type:
                domain.append(['membership_type', '=', membership_type])
            if state:
                domain.append(['state', '=', state])
            
            # Get members
            members = request.env['library.member'].search(domain, limit=limit, offset=offset)
            total_count = request.env['library.member'].search_count(domain)
            
            # Format response
            members_data = []
            for member in members:
                members_data.append({
                    'id': member.id,
                    'member_id': member.member_id,
                    'name': member.name,
                    'email': member.email,
                    'phone': member.phone,
                    'membership_type': member.membership_type,
                    'state': member.state,
                    'join_date': member.join_date.isoformat() if member.join_date else None,
                    'expiry_date': member.expiry_date.isoformat() if member.expiry_date else None,
                    'borrowed_count': member.borrowed_count,
                    'fine_amount': member.fine_amount,
                })
            
            return self._json_response({
                'success': True,
                'data': members_data,
                'pagination': {
                    'total': total_count,
                    'limit': limit,
                    'offset': offset,
                    'has_next': (offset + limit) < total_count
                }
            })
            
        except Exception as e:
            _logger.error("API Members List Error: %s", str(e))
            return self._json_response({'error': 'Internal server error', 'code': 500}, 500)
    
    @http.route('/api/members/<int:member_id>', type='http', auth='user', methods=['GET'], csrf=False)
    def api_member_detail(self, member_id, **kw):
        """Get detailed information about a specific member"""
        access_check = self._check_api_access()
        if access_check:
            return self._json_response(access_check, 403)
        
        try:
            member = request.env['library.member'].browse(member_id)
            if not member.exists():
                return self._json_response({'error': 'Member not found', 'code': 404}, 404)
            
            # Check if user can access this member's data
            current_user = request.env.user
            if not current_user.has_group('library_management.group_library_librarian'):
                if not (current_user.library_member_id and current_user.library_member_id.id == member_id):
                    return self._json_response({'error': 'Access denied', 'code': 403}, 403)
            
            member_data = {
                'id': member.id,
                'member_id': member.member_id,
                'name': member.name,
                'email': member.email,
                'phone': member.phone,
                'mobile': member.mobile,
                'address': member.address,
                'city': member.city,
                'state': member.state,
                'membership_type': member.membership_type,
                'join_date': member.join_date.isoformat() if member.join_date else None,
                'expiry_date': member.expiry_date.isoformat() if member.expiry_date else None,
                'borrowed_count': member.borrowed_count,
                'total_borrowed': member.total_borrowed,
                'fine_amount': member.fine_amount,
                'max_books': member.max_books,
                'current_borrowings': [
                    {
                        'id': b.id,
                        'book_name': b.book_id.name,
                        'borrow_date': b.borrow_date.isoformat() if b.borrow_date else None,
                        'due_date': b.due_date.isoformat() if b.due_date else None,
                        'days_overdue': b.days_overdue,
                        'state': b.state
                    } for b in member.current_borrowings
                ],
                'pending_fines': [
                    {
                        'id': f.id,
                        'amount': f.amount,
                        'reason': f.reason,
                        'date_created': f.date_created.isoformat() if f.date_created else None,
                        'due_date': f.due_date.isoformat() if f.due_date else None
                    } for f in member.fine_ids.filtered(lambda x: x.state == 'pending')
                ]
            }
            
            return self._json_response({'success': True, 'data': member_data})
            
        except Exception as e:
            _logger.error("API Member Detail Error: %s", str(e))
            return self._json_response({'error': 'Internal server error', 'code': 500}, 500)
    
    # =============================================================================
    # BORROWING API ENDPOINTS
    # =============================================================================
    
    @http.route('/api/borrowings', type='http', auth='user', methods=['POST'], csrf=False)
    def api_create_borrowing(self, **kw):
        """Create a new book borrowing"""
        access_check = self._check_api_access()
        if access_check:
            return self._json_response(access_check, 403)
        
        # Only librarians can create borrowings via API
        if not request.env.user.has_group('library_management.group_library_librarian'):
            return self._json_response({'error': 'Librarian access required', 'code': 403}, 403)
        
        try:
            # Parse JSON data
            data = json.loads(request.httprequest.data.decode('utf-8'))
            
            member_id = data.get('member_id')
            book_id = data.get('book_id')
            
            if not member_id or not book_id:
                return self._json_response({'error': 'member_id and book_id are required', 'code': 400}, 400)
            
            # Validate member and book
            member = request.env['library.member'].browse(member_id)
            book = request.env['library.book'].browse(book_id)
            
            if not member.exists():
                return self._json_response({'error': 'Member not found', 'code': 404}, 404)
            if not book.exists():
                return self._json_response({'error': 'Book not found', 'code': 404}, 404)
            
            # Check if member can borrow
            can_borrow, message = member.can_borrow_book()
            if not can_borrow:
                return self._json_response({'error': message, 'code': 400}, 400)
            
            # Check book availability
            if not book.check_availability():
                return self._json_response({'error': 'Book not available', 'code': 400}, 400)
            
            # Create borrowing
            borrowing = request.env['library.borrowing'].create({
                'member_id': member_id,
                'book_id': book_id,
                'book_condition_borrow': data.get('book_condition_borrow', 'good'),
                'notes': data.get('notes', '')
            })
            
            return self._json_response({
                'success': True,
                'data': {
                    'id': borrowing.id,
                    'name': borrowing.name,
                    'borrow_date': borrowing.borrow_date.isoformat(),
                    'due_date': borrowing.due_date.isoformat(),
                    'state': borrowing.state
                }
            })
            
        except Exception as e:
            _logger.error("API Create Borrowing Error: %s", str(e))
            return self._json_response({'error': 'Internal server error', 'code': 500}, 500)
    
    @http.route('/api/borrowings/<int:borrowing_id>/return', type='http', auth='user', methods=['POST'], csrf=False)
    def api_return_book(self, borrowing_id, **kw):
        """Return a borrowed book"""
        access_check = self._check_api_access()
        if access_check:
            return self._json_response(access_check, 403)
        
        # Only librarians can return books via API
        if not request.env.user.has_group('library_management.group_library_librarian'):
            return self._json_response({'error': 'Librarian access required', 'code': 403}, 403)
        
        try:
            borrowing = request.env['library.borrowing'].browse(borrowing_id)
            if not borrowing.exists():
                return self._json_response({'error': 'Borrowing not found', 'code': 404}, 404)
            
            # Parse JSON data for book condition
            try:
                data = json.loads(request.httprequest.data.decode('utf-8'))
                book_condition_return = data.get('book_condition_return', 'good')
                notes = data.get('notes', '')
            except:
                book_condition_return = 'good'
                notes = ''
            
            # Update borrowing with return condition and notes
            borrowing.book_condition_return = book_condition_return
            if notes:
                borrowing.notes = (borrowing.notes or '') + f"\nReturn notes: {notes}"
            
            # Return the book
            borrowing.action_return()
            
            return self._json_response({
                'success': True,
                'message': 'Book returned successfully',
                'data': {
                    'id': borrowing.id,
                    'return_date': borrowing.return_date.isoformat(),
                    'fine_amount': borrowing.fine_amount,
                    'state': borrowing.state
                }
            })
            
        except Exception as e:
            _logger.error("API Return Book Error: %s", str(e))
            return self._json_response({'error': str(e), 'code': 500}, 500)
    
    # =============================================================================
    # SEARCH API ENDPOINTS
    # =============================================================================
    
    @http.route('/api/search', type='http', auth='user', methods=['GET'], csrf=False)
    def api_global_search(self, **kw):
        """Global search across books, authors, and categories"""
        access_check = self._check_api_access()
        if access_check:
            return self._json_response(access_check, 403)
        
        try:
            query = kw.get('q', '').strip()
            if not query:
                return self._json_response({'error': 'Search query required', 'code': 400}, 400)
            
            limit = int(kw.get('limit', 10))
            
            # Search books
            books = request.env['library.book'].search([
                '|', ('name', 'ilike', query),
                '|', ('isbn', 'ilike', query),
                ('description', 'ilike', query)
            ], limit=limit)
            
            # Search authors
            authors = request.env['library.author'].search([
                ('name', 'ilike', query)
            ], limit=limit)
            
            # Search categories
            categories = request.env['library.category'].search([
                ('name', 'ilike', query)
            ], limit=limit)
            
            return self._json_response({
                'success': True,
                'data': {
                    'books': [
                        {
                            'id': b.id,
                            'name': b.name,
                            'isbn': b.isbn,
                            'authors': [a.name for a in b.author_ids],
                            'available_copies': b.available_copies
                        } for b in books
                    ],
                    'authors': [
                        {
                            'id': a.id,
                            'name': a.name,
                            'book_count': a.book_count
                        } for a in authors
                    ],
                    'categories': [
                        {
                            'id': c.id,
                            'name': c.complete_name,
                            'book_count': c.book_count
                        } for c in categories
                    ]
                }
            })
            
        except Exception as e:
            _logger.error("API Global Search Error: %s", str(e))
            return self._json_response({'error': 'Internal server error', 'code': 500}, 500)