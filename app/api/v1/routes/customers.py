import logging

from app.logging_config import sanitize_for_logging

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.v1.schemas.schemas import CustomerCreate, CustomerUpdate
from app.api.v1.services.audit_service import get_ip_from_request, log_action
from app.api.v1.services.auth_service import verify_user_token
from app.api.v1.services.customer_service import (
    change_customer_is_active,
    check_customer_access,
    create_customer,
    list_customers_by_organization,
    search_customer_by_id,
    update_customers,
)

# Configure router
router = APIRouter(prefix="/v1")

@router.post("/customers", status_code=201)
async def create_customers(request: Request, customer: CustomerCreate, user_id: int = Depends(verify_user_token)):
    # Check access (owner + staff)
    if not await check_customer_access(user_id, customer.organization_id, allow_staff=True):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, create customer
    recent_customer = await create_customer(customer.organization_id,
                                            customer.name,
                                            customer.email,
                                            customer.phone,
                                            customer.is_active)
    if recent_customer:
        # ==== AUDIT LOGS ENTRY ====
        # Add new values to a dict and log action
        new_values = {
            "organization_id": customer.organization_id,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "is_active": customer.is_active
        }
    
        # Get IP Address
        ip_address = get_ip_from_request(request)
    
        # Log action
        await log_action(
            organization_id=customer.organization_id,
            actor_user_id=user_id,
            action='CREATE',
            entity_type='CUSTOMER',
            entity_id=recent_customer,
            old_values=None,
            new_values=new_values,
            metadata={"source": "api", "version": "1.0"},
            ip_address=ip_address
        )
        # ==== END OF AUDIT LOGS ENTRY ====

        # ==== STRUCTURED LOGGING ====
        logger.info(
            f"Customer created: id={recent_customer}, "
            f"org_id={customer.organization_id}"
        )

        success_dict = {
                "message": f"Customer has been successfully created. CustomerID = {recent_customer}, OrgID = {customer.organization_id}."
        }
        return success_dict

@router.get("/customers", status_code=200)
async def list_customers(organization_id: int, user_id: int = Depends(verify_user_token)):
    # Check access (root + owner + staff)
    if not await check_customer_access(user_id, organization_id, allow_staff=True):
        raise HTTPException(status_code=403, detail="You aren't allowed to view this information")

    # Else, get all customers registered under the organization
    registered_customers = await list_customers_by_organization(organization_id)

    # Return registered_customers
    return registered_customers

@router.get("/customers/{id}", status_code=200)
async def get_customer(id: int, user_id: int = Depends(verify_user_token)):
    # Check if the customer exists
    customer = await search_customer_by_id(id)

    # If not found, return 404
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found or doesn't exist.")

    # If it isn't a owner + owner + staff, return 403
    if not await check_customer_access(user_id, customer["organization_id"], allow_staff=True):
        raise HTTPException(status_code=403, detail="You aren't allowed to view this information.")
    

    # Else, return the customer info
    return customer

@router.patch("/customers/{id}", status_code=200)
async def update_customer(request: Request, id: int, customer_update: CustomerUpdate, user_id: int = Depends(verify_user_token)):
    # Check if the customer exists
    customer = await search_customer_by_id(id)
    
    # If not found, return 404
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found or doesn't exist.")

    # Check if the current user is a owner + staff
    if not await check_customer_access(user_id, customer["organization_id"], allow_staff=True):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, update the customers information
    updated_customer = await update_customers(id, customer_update.name, customer_update.email, customer_update.phone, customer_update.is_active)

    if updated_customer:
        # ==== AUDIT LOGS ENTRY ====
        # Add new values to a dict and log action
        old_values = customer
        new_values = {}
        if customer_update.name is not None: new_values["name"] = customer_update.name
        if customer_update.email is not None: new_values["email"] = customer_update.email
        if customer_update.phone is not None: new_values["phone"] = customer_update.phone
        if customer_update.is_active is not None: new_values["is_active"] = customer_update.is_active
    
        # Get IP Address
        ip_address = get_ip_from_request(request)
    
        # Get organization id
        customer_organization_id = int(customer["organization_id"]) if customer["organization_id"] else None
    
        # Log action
        await log_action(
            organization_id=customer_organization_id,
            actor_user_id=user_id,
            action='UPDATE',
            entity_type='CUSTOMER',
            entity_id=id,
            old_values=old_values,
            new_values=new_values,
            metadata={"source": "api", "version": "1.0"},
            ip_address=ip_address
        )
        # ==== END OF AUDIT LOGS ENTRY ====

        # ==== STRUCTURED LOGGING ====
        logger.info(
            f"Customer updated: id={id}, "
            f"org_id={customer_organization_id}, "
            f"email={sanitize_for_logging(new_values.get('email'), 'email') if 'email' in new_values else 'N/A'}, "
            f"phone={sanitize_for_logging(new_values.get('phone'), 'phone') if 'phone' in new_values else 'N/A'}, "
            f"updated_fields={[f for f in new_values.key() if f not in ['email', 'phone']]}"
        )

        return updated_customer

@router.delete("/customers/{id}", status_code=200)
async def delete_customer(request: Request, id: int, user_id: int = Depends(verify_user_token)):
    # Check if the customer exists
    customer = await search_customer_by_id(id)

    # If not found, return 404
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found or doesn't exist.")

    # Check if the current user is a owner or professional
    if not await check_customer_access(user_id, customer["organization_id"], allow_staff=True):
        raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

    # Else, deactivate the user
    is_deleted = await change_customer_is_active(id, False)

    if is_deleted:
        # ==== AUDIT LOGS ENTRY ====
        # Add new values to a dict and log action
        old_values = customer
        new_values = {
            "is_active": False
        }
    
        # Get IP Address
        ip_address = get_ip_from_request(request)
    
        # Get organization id
        customer_organization_id = int(customer["organization_id"]) if customer["organization_id"] else None
    
        # Log action
        await log_action(
            organization_id=customer_organization_id,
            actor_user_id=user_id,
            action='DELETE',
            entity_type='CUSTOMER',
            entity_id=id,
            old_values=old_values,
            new_values=new_values,
            metadata={"source": "api", "version": "1.0"},
            ip_address=ip_address
        )
        # ==== END OF AUDIT LOGS ENTRY ====

        # ==== STRUCTURED LOGGING ====
        logger.info(
            f"Customer deleted: id={id}, "
            f"org_id={customer_organization_id}"
        )

        success_dict = {
            "message": f"Customer {id} has been successfully deactivated."
        }
        return success_dict