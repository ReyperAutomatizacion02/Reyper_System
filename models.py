from flask_login import UserMixin

class User(UserMixin):
    def __init__(self, id, email, username=None, roles=None):
        self.id = id
        self.email = email
        self.username = username
        self.roles = roles or []
    
    @property
    def is_admin(self):
        return 'Admin' in self.roles
        
    @property
    def is_sales(self):
        return 'Ventas' in self.roles
