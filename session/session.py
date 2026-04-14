
# session/session.py
class Session:
    current_user = None
    tenant_id = None
    user_role = "employee"

    @classmethod
    def start(cls, user, tenant_id, role="employee"):
        cls.current_user = user
        cls.tenant_id = tenant_id
        cls.user_role = role

    @classmethod
    def end(cls):
        cls.current_user = None
        cls.tenant_id = None
        cls.user_role = "employee"

    @classmethod
    def is_authenticated(cls):
        return cls.current_user is not None

    @classmethod
    def get_email_initial(cls):
        if cls.current_user and cls.current_user.email:
            return cls.current_user.email[0].upper()
        return "U"

    @classmethod
    def get_email(cls):
        if cls.current_user:
            return cls.current_user.email
        return ""