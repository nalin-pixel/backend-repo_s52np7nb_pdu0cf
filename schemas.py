"""
Database Schemas for Elitemoney Pro Manager

Each Pydantic model maps to a MongoDB collection using the lowercase
name of the class (e.g., User -> "user").
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime

# Users
class User(BaseModel):
    """Users collection schema"""
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    default_workspace_id: Optional[str] = Field(None, description="Default workspace ID")

# Workspaces
class Workspace(BaseModel):
    """Workspaces collection schema"""
    name: str = Field(..., description="Workspace name")
    type: Literal["company", "home", "social"] = Field(..., description="Workspace type")
    members: List[str] = Field(default_factory=list, description="List of user IDs")

# Transactions
class Beneficiary(BaseModel):
    user_id: str
    share: Optional[float] = Field(None, description="Percentage share (0-1) or amount depending on split method")

class Transaction(BaseModel):
    """Transactions collection schema"""
    workspace_id: str
    type: Literal["company", "home", "social"] = Field(...)
    amount: float = Field(..., gt=0)
    date: datetime = Field(default_factory=datetime.utcnow)
    category: str = Field("General")
    status: Literal["Pending", "Cleared"] = Field("Pending")
    # Company/Home specific
    direction: Optional[Literal["income", "expense"]] = Field(None, description="Cash direction for budgets/cash flow")
    # Social specific
    payer_id: Optional[str] = None
    split_method: Optional[Literal["equal", "percentage"]] = None
    beneficiaries: Optional[List[Beneficiary]] = None

# Notifications
class Notification(BaseModel):
    workspace_id: str
    user_id: Optional[str] = None
    title: str
    message: str
    priority: Literal["low", "normal", "high"] = "normal"
    seen: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
