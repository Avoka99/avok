import sys

def patch_user_model():
    filepath = 'c:/Users/User/Desktop/AvokProject/app/models/user.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Enum UserStatus
    old_enum = """    SUSPENDED = "suspended"
    BANNED = "banned\""""
    new_enum = """    SUSPENDED = "suspended"
    BANNED = "banned"
    DEACTIVATED = "deactivated\""""
    if old_enum in content:
        content = content.replace(old_enum, new_enum)

    # Imports
    if ', JSON' not in content and ' JSON' not in content:
        content = content.replace('Column, String, Boolean, DateTime, Enum, Integer, Text, ForeignKey, Index', 'Column, String, Boolean, DateTime, Enum, Integer, Text, ForeignKey, Index, JSON')

    # KYC Fields
    old_kyc = """    # KYC Information
    kyc_status = Column(Enum(KYCStatus), default=KYCStatus.NOT_SUBMITTED)
    ghana_card_number = Column(String(50), unique=True, nullable=True)
    ghana_card_image_url = Column(String(500), nullable=True)
    selfie_image_url = Column(String(500), nullable=True)"""
    new_kyc = """    # KYC Information
    kyc_status = Column(Enum(KYCStatus), default=KYCStatus.NOT_SUBMITTED)
    national_id_type = Column(String(50), nullable=True)
    national_id_number = Column(String(50), index=True, nullable=True)
    national_id_image_url = Column(String(500), nullable=True)
    selfie_image_url = Column(String(500), nullable=True)
    kyc_approvals = Column(JSON, default=list, nullable=True)"""
    if old_kyc in content:
        content = content.replace(old_kyc, new_kyc)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def patch_user_schema():
    filepath = 'c:/Users/User/Desktop/AvokProject/app/schemas/user.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    old_sub = """class KYCSubmission(BaseModel):
    ghana_card_number: str
    ghana_card_image: str  # Base64 or S3 URL
    selfie_image: str  # Base64 or S3 URL"""
    new_sub = """class KYCSubmission(BaseModel):
    document_type: str
    document_number: str
    document_image: str  # Base64 or S3 URL
    selfie_image: str  # Base64 or S3 URL"""
    
    if old_sub in content:
        content = content.replace(old_sub, new_sub)
        
    # UserUpdate schema
    if "ghana_card_number: Optional[str]" in content:
        content = content.replace("ghana_card_number: Optional[str]", "national_id_number: Optional[str]")

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def patch_auth_service():
    filepath = 'c:/Users/User/Desktop/AvokProject/app/services/auth.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if "ExternalKYCProvider" not in content:
        content = "from app.services.kyc_provider import ExternalKYCProvider\n" + content

    old_submit = """    async def submit_kyc(
        self,
        user_id: int,
        ghana_card_number: str,
        ghana_card_image_url: str,
        selfie_image_url: str
    ) -> User:
        \"\"\"Submit KYC documents.\"\"\"
        user = await self._get_user(user_id)
        
        if not user:
            raise NotFoundError("User", user_id)
        
        # Validate Ghana Card number
        if not self._validate_ghana_card(ghana_card_number):
            raise ValidationError("Invalid Ghana Card number format")
        
        # Check if card already used
        existing = await self._get_user_by_ghana_card(ghana_card_number)
        if existing and existing.id != user_id:
            raise ValidationError("Ghana Card number already registered")
        
        user.ghana_card_number = ghana_card_number
        user.ghana_card_image_url = ghana_card_image_url
        user.selfie_image_url = selfie_image_url
        user.kyc_status = KYCStatus.PENDING
        
        await self.db.commit()
        
        # Notify admins for review
        await self._notify_admins_kyc_pending(user)
        
        logger.info(f"KYC submitted for user {user_id}")
        return user"""
        
    new_submit = """    async def submit_kyc(
        self,
        user_id: int,
        document_type: str,
        document_number: str,
        document_image_url: str,
        selfie_image_url: str
    ) -> User:
        \"\"\"Submit KYC documents with dynamic checks.\"\"\"
        user = await self._get_user(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        
        # Check historical reuse excluding DEACTIVATED
        existing_matches = await self.db.execute(
            select(User).where(User.national_id_number == document_number)
        )
        for existing in existing_matches.scalars().all():
            if existing.id != user_id and existing.status != UserStatus.DEACTIVATED:
                raise ValidationError("Document already registered to an active or banned account")
        
        # Abstract verification
        external_result = await ExternalKYCProvider.verify_document_and_background(
            document_type, document_number, document_image_url, selfie_image_url
        )
        
        user.national_id_type = document_type
        user.national_id_number = document_number
        user.national_id_image_url = document_image_url
        user.selfie_image_url = selfie_image_url
        user.kyc_approvals = [] # Wipe old approvals
        
        if external_result["status"] == "flagged":
            user.is_flagged = True
            user.kyc_status = KYCStatus.PENDING # Keep pending so 2 admins can override
            logger.warning(f"User {user_id} flagged during external KYC: {external_result['reasons']}")
        else:
            user.is_flagged = False
            user.kyc_status = KYCStatus.PENDING
            
        await self.db.commit()
        await self._notify_admins_kyc_pending(user)
        return user"""
        
    if old_submit in content:
        content = content.replace(old_submit, new_submit)

    old_approve = """    async def approve_kyc(self, user_id: int, admin_id: int) -> User:
        \"\"\"Approve KYC verification.\"\"\"
        user = await self._get_user(user_id)
        
        if user.kyc_status != KYCStatus.PENDING:
            raise ValidationError("KYC not pending approval")
        
        user.kyc_status = KYCStatus.VERIFIED
        
        # Update user status if still pending
        if user.status == UserStatus.PENDING and user.is_phone_verified:
            user.status = UserStatus.ACTIVE
        
        await self.db.commit()
        
        # Send notification
        await self.notification_service.send_kyc_approved(user.phone_number)
        
        logger.info(f"KYC approved for user {user_id} by admin {admin_id}")
        return user"""
        
    new_approve = """    async def approve_kyc(self, user_id: int, admin_id: int) -> User:
        \"\"\"Approve KYC dynamically (1 for clean, 2 for flagged).\"\"\"
        user = await self._get_user(user_id)
        
        if user.kyc_status != KYCStatus.PENDING:
            raise ValidationError("KYC not pending approval")
            
        approvals = list(user.kyc_approvals or [])
        if admin_id not in approvals:
            approvals.append(admin_id)
            user.kyc_approvals = approvals
            
        required_approvals = 2 if user.is_flagged else 1
        
        if len(set(approvals)) >= required_approvals:
            user.kyc_status = KYCStatus.VERIFIED
            if user.status == UserStatus.PENDING and user.is_phone_verified:
                user.status = UserStatus.ACTIVE
            
            await self.notification_service.send_kyc_approved(user.phone_number)
            logger.info(f"KYC completely approved for user {user_id} by {len(set(approvals))} admins.")
        else:
            logger.info(f"KYC partially approved for user {user_id} by admin {admin_id}. Needs {required_approvals}")
            
        await self.db.commit()
        return user"""
        
    if old_approve in content:
        content = content.replace(old_approve, new_approve)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def patch_auth_api():
    filepath = 'c:/Users/User/Desktop/AvokProject/app/api/v1/auth.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    old_api = """    user = await auth_service.submit_kyc(
        user_id=current_user.id,
        ghana_card_number=payload.ghana_card_number,
        ghana_card_image_url=payload.ghana_card_image,
        selfie_image_url=payload.selfie_image,
    )"""
    new_api = """    user = await auth_service.submit_kyc(
        user_id=current_user.id,
        document_type=payload.document_type,
        document_number=payload.document_number,
        document_image_url=payload.document_image,
        selfie_image_url=payload.selfie_image,
    )"""
    
    if old_api in content:
        content = content.replace(old_api, new_api)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

if __name__ == "__main__":
    patch_user_model()
    patch_user_schema()
    patch_auth_service()
    patch_auth_api()
    print("Patched Python advanced KYC.")
