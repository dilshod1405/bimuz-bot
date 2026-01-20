"""API client for communicating with the backend."""
import aiohttp  # type: ignore
import json
from typing import Optional, Dict, Any, List
from config import API_BASE_URL
from storage import user_storage
import logging

logger = logging.getLogger(__name__)

# Timeout configuration (in seconds)
# Increased timeouts for better reliability with external APIs
TIMEOUT = aiohttp.ClientTimeout(
    total=180,  # Total timeout for the entire request (3 minutes)
    connect=90,  # Timeout for establishing connection (1.5 minutes)
    sock_read=90  # Timeout for reading data (1.5 minutes)
)


class APIClient:
    """Client for making API requests to the backend."""
    
    def __init__(self, access_token: Optional[str] = None, user_id: Optional[int] = None):
        self.base_url = API_BASE_URL
        self.access_token = access_token
        self.user_id = user_id
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=TIMEOUT)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        headers = {
            'Content-Type': 'application/json',
        }
        if self.access_token:
            headers['Authorization'] = f'Bearer {self.access_token}'
        return headers
    
    async def _refresh_access_token(self) -> Optional[str]:
        """Refresh access token if user_id is provided."""
        if not self.user_id:
            return None
        
        refresh_token = await user_storage.get_refresh_token(self.user_id)
        if not refresh_token:
            return None
        
        try:
            async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
                url = f"{self.base_url}/api/v1/auth/token/refresh/"
                async with session.post(
                    url,
                    json={'refresh': refresh_token},
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    if response.status == 200:
                        response_data = await response.json()
                        new_access_token = response_data.get('access')
                        if new_access_token:
                            await user_storage.update_access_token(self.user_id, new_access_token)
                            return new_access_token
        except Exception as e:
            logger.error(f"Token refresh error: {str(e)}")
        
        return None
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        retry_on_401: bool = True,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """Make an API request with retry logic for network errors."""
        if not self.session:
            self.session = aiohttp.ClientSession(timeout=TIMEOUT)
        
        # Ensure endpoint starts with /
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        
        # Ensure base_url doesn't end with /
        base_url = self.base_url.rstrip('/')
        url = f"{base_url}{endpoint}"
        headers = self._get_headers()
        
        logger.info(f"Making {method} request to: {url}")
        if data:
            logger.debug(f"Request data: {str(data)[:200]}")
        if params:
            logger.debug(f"Request params: {params}")
        
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"Sending {method} request (attempt {attempt + 1}/{max_retries + 1})...")
                async with self.session.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params,
                    headers=headers
                ) as response:
                    logger.info(f"Response received: status={response.status}, headers={dict(response.headers)}")
                    # Handle 204 No Content (common for DELETE requests)
                    if response.status == 204:
                        # Some backends return 204 with JSON body despite HTTP spec
                        # Try to read body, but don't fail if it's empty or unreadable
                        try:
                            # Check if there's content to read
                            content_length = response.headers.get('Content-Length', '0')
                            if content_length and int(content_length) > 0:
                                text = await response.read()
                                if text:
                                    try:
                                        response_data = json.loads(text.decode('utf-8'))
                                        if response_data.get('success'):
                                            return response_data
                                    except (json.JSONDecodeError, UnicodeDecodeError):
                                        pass
                            # If no body or parsing failed, return success
                            return {'success': True, 'message': 'Operation completed successfully'}
                        except Exception as e:
                            # If any error reading 204 response, assume success
                            logger.debug(f"204 response handling for {url}: {str(e)}")
                            return {'success': True, 'message': 'Operation completed successfully'}
                    
                    # Try to parse JSON response
                    try:
                        response_data = await response.json()
                    except (aiohttp.ContentTypeError, json.JSONDecodeError) as e:
                        # If response is not JSON, get text
                        text = await response.text()
                        logger.error(f"JSON parsing error for {url}: {text[:200]}")
                        raise Exception(f"Invalid JSON response: {text[:200]}")
                    
                    # Handle 401 Unauthorized - try to refresh token
                    if response.status == 401 and retry_on_401 and self.user_id:
                        new_token = await self._refresh_access_token()
                        if new_token:
                            self.access_token = new_token
                            headers = self._get_headers()
                            # Retry the request with new token
                            async with self.session.request(
                                method=method,
                                url=url,
                                json=data,
                                params=params,
                                headers=headers
                            ) as retry_response:
                                # Handle 204 No Content on retry
                                if retry_response.status == 204:
                                    try:
                                        content_length = retry_response.headers.get('Content-Length', '0')
                                        if content_length and int(content_length) > 0:
                                            text = await retry_response.read()
                                            if text:
                                                try:
                                                    response_data = json.loads(text.decode('utf-8'))
                                                    if response_data.get('success'):
                                                        return response_data
                                                except (json.JSONDecodeError, UnicodeDecodeError):
                                                    pass
                                        return {'success': True, 'message': 'Operation completed successfully'}
                                    except Exception:
                                        return {'success': True, 'message': 'Operation completed successfully'}
                                
                                try:
                                    response_data = await retry_response.json()
                                except (aiohttp.ContentTypeError, json.JSONDecodeError) as e:
                                    text = await retry_response.text()
                                    logger.error(f"JSON parsing error on retry for {url}: {text[:200]}")
                                    raise Exception(f"Invalid JSON response: {text[:200]}")
                                
                                if retry_response.status >= 400:
                                    # For 400 errors, return the response data instead of raising exception
                                    if retry_response.status == 400:
                                        return {
                                            'success': False,
                                            'message': response_data.get('message', 'Validation error'),
                                            'errors': response_data.get('errors', response_data)
                                        }
                                    error_msg = response_data.get('message', 'Unknown error')
                                    errors = response_data.get('errors', {})
                                    if errors:
                                        error_msg += f" - {errors}"
                                    raise Exception(f"API Error ({retry_response.status}): {error_msg}")
                                
                                return response_data
                        else:
                            # Token refresh failed, user needs to login again
                            raise Exception("Authentication failed. Please login again.")
                    
                    if response.status >= 400:
                        # For 400 errors, return the response data instead of raising exception
                        # This allows handlers to check response.get('success') and handle errors gracefully
                        if response.status == 400:
                            # Return error response in same format as success response
                            return {
                                'success': False,
                                'message': response_data.get('message', 'Validation error'),
                                'errors': response_data.get('errors', response_data)
                            }
                        error_msg = response_data.get('message', 'Unknown error')
                        errors = response_data.get('errors', {})
                        if errors:
                            if isinstance(errors, dict):
                                error_msg += f" - {errors}"
                            else:
                                error_msg += f" - {str(errors)}"
                        raise Exception(f"API Error ({response.status}): {error_msg}")
                    
                    return response_data
            except aiohttp.ClientError as e:
                error_str = str(e)
                # Check if it's a 204 parsing issue - if so, assume success
                if "204" in error_str or "Expected HTTP" in error_str or "RTSP" in error_str or "ICE" in error_str:
                    logger.debug(f"204 response parsing issue for {url}, assuming success: {str(e)}")
                    return {'success': True, 'message': 'Operation completed successfully'}
                
                last_error = e
                # Retry on network errors (timeout, connection errors, etc.)
                if attempt < max_retries:
                    wait_time = (attempt + 1) * 2  # Exponential backoff: 2s, 4s
                    logger.warning(f"Network error for {url} (attempt {attempt + 1}/{max_retries + 1}): {str(e)}. Retrying in {wait_time}s...")
                    import asyncio
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Network error for {url} after {max_retries + 1} attempts: {str(e)}")
                    error_type = type(e).__name__
                    error_msg = str(e)
                    # Provide more specific error message
                    if "timeout" in error_msg.lower() or "TimeoutError" in error_type:
                        raise Exception(f"Connection timeout to host {url}. Please check API_BASE_URL ({self.base_url}) and network connectivity.")
                    elif "Connection" in error_type or "connection" in error_msg.lower():
                        raise Exception(f"Connection error to {url}. Please check if API server is running and accessible.")
                    else:
                        raise Exception(f"Network error: [{error_type}] {error_msg}")
            except Exception as e:
                # Don't retry on non-network errors
                raise
    
    # Authentication endpoints
    async def login(self, email: str, password: str) -> Dict[str, Any]:
        """Login employee."""
        return await self._request('POST', '/api/v1/auth/login/', {
            'email': email,
            'password': password
        })
    
    async def get_profile(self) -> Dict[str, Any]:
        """Get employee profile."""
        return await self._request('GET', '/api/v1/auth/profile/')
    
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token."""
        return await self._request('POST', '/api/v1/auth/token/refresh/', {
            'refresh': refresh_token
        })
    
    # Employee endpoints
    async def get_employees(self, search: Optional[str] = None) -> Dict[str, Any]:
        """Get list of employees."""
        params = {}
        if search:
            params['search'] = search
        response = await self._request('GET', '/api/v1/auth/employees/', params=params)
        # Backend can return either pagination format or success_response format
        # Pagination: {'count': ..., 'next': ..., 'results': [...]}
        # Success: {'success': True, 'data': [...]}
        return response
    
    async def get_employee(self, employee_id: int) -> Dict[str, Any]:
        """Get employee by ID."""
        return await self._request('GET', f'/api/v1/auth/employees/{employee_id}/')
    
    async def create_employee(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new employee (requires Developer role)."""
        # Employee registration doesn't require authentication token
        # But we still pass it if available for logging purposes
        return await self._request('POST', '/api/v1/auth/register/', data, retry_on_401=False)
    
    async def update_employee(self, employee_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update employee."""
        return await self._request('PATCH', f'/api/v1/auth/employees/{employee_id}/', data)
    
    async def delete_employee(self, employee_id: int) -> Dict[str, Any]:
        """Delete employee."""
        return await self._request('DELETE', f'/api/v1/auth/employees/{employee_id}/')
    
    # Student endpoints
    async def get_students(self, search: Optional[str] = None) -> Dict[str, Any]:
        """Get list of students."""
        params = {}
        if search:
            params['search'] = search
        response = await self._request('GET', '/api/v1/auth/students/', params=params)
        # Backend can return either pagination format or success_response format
        return response
    
    async def get_student(self, student_id: int) -> Dict[str, Any]:
        """Get student by ID."""
        return await self._request('GET', f'/api/v1/auth/students/{student_id}/')
    
    async def create_student(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new student (for employees - requires Developer or Administrator role)."""
        return await self._request('POST', '/api/v1/auth/students/', data)
    
    async def update_student(self, student_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update student."""
        return await self._request('PATCH', f'/api/v1/auth/students/{student_id}/', data)
    
    async def delete_student(self, student_id: int) -> Dict[str, Any]:
        """Delete student."""
        return await self._request('DELETE', f'/api/v1/auth/students/{student_id}/')
    
    # Group endpoints
    async def get_groups(self) -> Dict[str, Any]:
        """Get list of groups."""
        response = await self._request('GET', '/api/v1/education/groups/')
        # Backend can return either pagination format or success_response format
        return response
    
    async def get_group(self, group_id: int) -> Dict[str, Any]:
        """Get group by ID."""
        return await self._request('GET', f'/api/v1/education/groups/{group_id}/')
    
    async def create_group(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new group."""
        return await self._request('POST', '/api/v1/education/groups/', data)
    
    async def update_group(self, group_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update group."""
        return await self._request('PATCH', f'/api/v1/education/groups/{group_id}/', data)
    
    async def delete_group(self, group_id: int) -> Dict[str, Any]:
        """Delete group."""
        return await self._request('DELETE', f'/api/v1/education/groups/{group_id}/')
    
    # Attendance endpoints
    async def get_attendances(self) -> Dict[str, Any]:
        """Get list of attendances."""
        response = await self._request('GET', '/api/v1/education/attendances/')
        # Backend can return either pagination format or success_response format
        return response
    
    async def get_attendance(self, attendance_id: int) -> Dict[str, Any]:
        """Get attendance by ID."""
        return await self._request('GET', f'/api/v1/education/attendances/{attendance_id}/')
    
    async def create_attendance(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new attendance."""
        return await self._request('POST', '/api/v1/education/attendances/', data)
    
    # Invoice/Payment endpoints
    async def get_invoices(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        ordering: Optional[str] = None,
        page: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get list of invoices."""
        params = {}
        if search:
            params['search'] = search
        if status:
            params['status'] = status
        if ordering:
            params['ordering'] = ordering
        if page:
            params['page'] = page
        response = await self._request('GET', '/api/v1/payment/employee-invoices/', params=params)
        # Backend can return either pagination format or success_response format
        return response
    
    async def get_invoice(self, invoice_id: int) -> Dict[str, Any]:
        """Get invoice by ID."""
        return await self._request('GET', f'/api/v1/payment/invoices/{invoice_id}/')
    
    async def create_payment_link(self, invoice_id: int, return_url: Optional[str] = None) -> Dict[str, Any]:
        """Create payment link for invoice."""
        data = {'invoice_id': invoice_id}
        if return_url:
            data['return_url'] = return_url
        return await self._request('POST', '/api/v1/payment/create-payment/', data)
    
    # Booking endpoints
    async def get_booking_groups(self) -> Dict[str, Any]:
        """Get groups available for booking."""
        return await self._request('GET', '/api/v1/education/booking/groups/')
    
    async def book_student(self, student_id: int, group_id: int) -> Dict[str, Any]:
        """Book a student into a group."""
        return await self._request('POST', '/api/v1/education/booking/book/', {
            'student_id': student_id,
            'group_id': group_id
        })
    
    async def cancel_booking(self, student_id: int) -> Dict[str, Any]:
        """Cancel student booking."""
        return await self._request('POST', '/api/v1/education/booking/cancel/', {
            'student_id': student_id
        })
    
    async def change_group(self, student_id: int, new_group_id: int) -> Dict[str, Any]:
        """Change student's group."""
        return await self._request('POST', '/api/v1/education/booking/change-group/', {
            'student_id': student_id,
            'new_group_id': new_group_id
        })
