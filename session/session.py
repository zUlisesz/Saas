# app/session/session.py

class Session:
    current_user = None
    tenant_id = None

    @classmethod
    def start(cls, user, tenant_id):
        cls.current_user = user
        cls.tenant_id = tenant_id
        print(f"[SESSION] Usuario: {user.email} | Tenant: {tenant_id}")

    @classmethod
    def end(cls):
        cls.current_user = None
        cls.tenant_id = None