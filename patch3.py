import sys

def patch_user_model():
    filepath = 'c:/Users/User/Desktop/AvokProject/app/models/user.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    old = """    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)"""
    new = """    # Avok Account System
    avok_account_number = Column(String(20), unique=True, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)"""
    
    if old in content:
        content = content.replace(old, new)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

def patch_user_schema():
    filepath = 'c:/Users/User/Desktop/AvokProject/app/schemas/user.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    old1 = """class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    
    @field_validator"""
    new1 = """class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    wants_avok_account: bool = False
    
    @field_validator"""
    
    old2 = """    id: int
    status: UserStatus
    kyc_status: KYCStatus
    is_phone_verified: bool
    created_at: datetime"""
    new2 = """    id: int
    avok_account_number: Optional[str] = None
    status: UserStatus
    kyc_status: KYCStatus
    is_phone_verified: bool
    created_at: datetime"""

    if old1 in content and old2 in content:
        content = content.replace(old1, new1)
        content = content.replace(old2, new2)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

def patch_auth_service():
    filepath = 'c:/Users/User/Desktop/AvokProject/app/services/auth.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Add random import
    if 'import random' not in content:
        content = content.replace('import secrets', 'import secrets\nimport random')

    # Add method
    new_method = """    def _generate_account_number(self) -> str:
        return "".join([str(random.randint(0,9)) for _ in range(10)])
        
    async def allocate_avok_account(self, user_id: int) -> User:
        user = await self._get_user(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        if user.avok_account_number:
            raise ValidationError("User already has an Avok account number")
            
        while True:
            acct = self._generate_account_number()
            existing = await self.db.execute(select(User).where(User.avok_account_number == acct))
            if not existing.scalar_one_or_none():
                user.avok_account_number = acct
                break
                
        await self.db.commit()
        return user
"""
    if 'def _generate_account_number' not in content:
        content += "\n" + new_method

    # Upgrade register
    old_register = """        # Create user
        user = User(
            email=user_data.email,
            phone_number=user_data.phone_number,
            hashed_password=get_password_hash(user_data.password),
            full_name=user_data.full_name,
            role=user_data.role,
            status=UserStatus.PENDING
        )"""
    new_register = """        # Create user
        user = User(
            email=user_data.email,
            phone_number=user_data.phone_number,
            hashed_password=get_password_hash(user_data.password),
            full_name=user_data.full_name,
            role=user_data.role,
            status=UserStatus.PENDING,
            avok_account_number=self._generate_account_number() if getattr(user_data, 'wants_avok_account', False) else None
        )"""
    
    if old_register in content:
        content = content.replace(old_register, new_register)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

def patch_auth_api():
    filepath = 'c:/Users/User/Desktop/AvokProject/app/api/v1/auth.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    new_endpoint = """
@router.post("/allocate-account", response_model=UserResponse)
async def allocate_account(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    \"\"\"Allocate an Avok account number to user.\"\"\"
    auth_service = AuthService(db)
    try:
        user = await auth_service.allocate_avok_account(current_user.id)
        return user
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
"""
    if 'allocate_account' not in content:
        content += new_endpoint
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

if __name__ == "__main__":
    patch_user_model()
    patch_user_schema()
    patch_auth_service()
    patch_auth_api()
    print("Patched Python files.")
