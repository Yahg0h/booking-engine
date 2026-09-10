from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.schemas.schemas import CustomerCreate, CustomerUpdate
from app.api.v1.services.auth_service import verify_user_token
from app.api.v1.services.customer_service import (
        change_customer_is_active,
        create_customer,
        list_customers_by_organization,
        search_customer_by_id,
        update_customers,
)
from app.api.v1.services.permission_service import is_root

# Configure router
router = APIRouter(prefix="/v1/root")

@router.post("/customers", status_code=201)
async def create_customers(customer: CustomerCreate, user_id: int = Depends(verify_user_token)):
    # Check the current user's access
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")

    # Else, create customer
    recent_customer = await create_customer(customer.organization_id,
                                            customer.name,
                                            customer.email,
                                            customer.phone,
                                            customer.is_active)
    if recent_customer:
        success_dict = {
                "message": f"ROOT: Customer has been successfully created. CustomerID = {recent_customer}, OrgID = {customer.organization_id}."
        }
        return success_dict

@router.get("/customers", status_code=200)
async def list_customers(organization_id: int, user_id: int = Depends(verify_user_token)):
    # Check access
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")

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

    # Check the current user's access
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")
    

    # Else, return the customer info
    return customer

@router.patch("/customers/{id}", status_code=200)
async def update_customer(id: int, customer_update: CustomerUpdate, user_id: int = Depends(verify_user_token)):
    # Check if the customer exists
    customer = await search_customer_by_id(id)
    
    # If not found, return 404
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found or doesn't exist.")

    # Check the current user's access
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")

    # Else, update the customers information
    updated_customer = await update_customers(id, customer_update.name, customer_update.email, customer_update.phone, customer_update.is_active)

    if updated_customer:
        return updated_customer

@router.delete("/customers/{id}", status_code=200)
async def delete_customer(id: int, user_id: int = Depends(verify_user_token)):
    # Check if the customer exists
    customer = await search_customer_by_id(id)

    # If not found, return 404
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found or doesn't exist.")

    # Check the current user's access
    if not await is_root(user_id):
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource.")

    # Else, deactivate the user
    is_deleted = await change_customer_is_active(id, False)

    if is_deleted:
        success_dict = {
            "message": f"ROOT: Customer {id} has been successfully deactivated."
        }
        return success_dict