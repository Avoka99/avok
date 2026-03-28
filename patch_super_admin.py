import sys

def patch_dependencies():
    filepath = 'c:/Users/User/Desktop/AvokProject/app/api/dependencies.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    new_dep = """
async def get_current_super_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    \"\"\"Get current super admin user.\"\"\"
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super Admin privileges strictly required",
        )
    return current_user
"""
    if "get_current_super_admin" not in content:
        content += new_dep
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

def patch_schema():
    filepath = 'c:/Users/User/Desktop/AvokProject/app/schemas/user.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    new_schema = """
class AdminRoleRequest(BaseModel):
    phone_number: str
"""
    if "AdminRoleRequest" not in content:
        content += new_schema
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

def patch_auth_service():
    filepath = 'c:/Users/User/Desktop/AvokProject/app/services/auth.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    new_methods = """
    async def appoint_admin(self, phone_number: str) -> User:
        user = await self._get_user_by_phone(phone_number)
        if not user:
            raise NotFoundError("User", phone_number)
        if user.role == UserRole.SUPER_ADMIN:
            raise ValidationError("Cannot downgrade a Super Admin to standard Admin")
            
        user.role = UserRole.ADMIN
        await self.db.commit()
        return user

    async def dismiss_admin(self, phone_number: str) -> User:
        user = await self._get_user_by_phone(phone_number)
        if not user:
            raise NotFoundError("User", phone_number)
        if user.role == UserRole.SUPER_ADMIN:
            raise ValidationError("Cannot dismiss a Super Admin")
            
        user.role = UserRole.BUYER
        await self.db.commit()
        return user
"""
    if "appoint_admin" not in content:
        content += new_methods
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

def patch_auth_api():
    filepath = 'c:/Users/User/Desktop/AvokProject/app/api/v1/auth.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Import fix
    if "get_current_super_admin" not in content:
        content = content.replace("from app.api.dependencies import get_db, get_current_user", "from app.api.dependencies import get_db, get_current_user, get_current_super_admin")
    
    if "AdminRoleRequest" not in content:
        content = content.replace("PhoneVerificationRequest, KYCSubmission", "PhoneVerificationRequest, KYCSubmission, AdminRoleRequest")

    new_endpoints = """
@router.post("/roles/appoint-admin", response_model=UserResponse)
async def appoint_admin(
    payload: AdminRoleRequest,
    current_super_admin=Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db)
):
    \"\"\"Appoint a new Admin. Only Super Admins can do this.\"\"\"
    auth_service = AuthService(db)
    user = await auth_service.appoint_admin(payload.phone_number)
    return user

@router.post("/roles/dismiss-admin", response_model=UserResponse)
async def dismiss_admin(
    payload: AdminRoleRequest,
    current_super_admin=Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db)
):
    \"\"\"Dismiss an Admin. Only Super Admins can do this.\"\"\"
    auth_service = AuthService(db)
    user = await auth_service.dismiss_admin(payload.phone_number)
    return user
"""
    if "appoint_admin" not in content:
        content += new_endpoints
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

def patch_seed():
    filepath = 'c:/Users/User/Desktop/AvokProject/scripts/seed_local_data.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Remove 0243333333 totally and replace with Benjee
    old_users = """    {
        "phone_number": "0243333333",
        "full_name": "Local Admin",
        "email": "admin@avok.local",
        "role": UserRole.ADMIN,
    },"""
    new_users = """    {
        "phone_number": "0559211947",
        "full_name": "God Admin",
        "email": "god@avok.local",
        "role": UserRole.SUPER_ADMIN,
    },"""

    if old_users in content:
        content = content.replace(old_users, new_users)

    # Change password mapping specifically for Super Admin
    old_user_creation = """                    hashed_password=get_password_hash(DEFAULT_PASSWORD),"""
    new_user_creation = """                    hashed_password=get_password_hash("Benjee99.av" if payload["role"] == UserRole.SUPER_ADMIN else DEFAULT_PASSWORD),"""
    
    if old_user_creation in content:
        content = content.replace(old_user_creation, new_user_creation)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


if __name__ == "__main__":
    patch_dependencies()
    patch_schema()
    patch_auth_service()
    patch_auth_api()
    patch_seed()
    print("Patched Super Admin backend logic.")
