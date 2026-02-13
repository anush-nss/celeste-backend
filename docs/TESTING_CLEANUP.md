# Testing Logic Cleanup Guide

This document outlines the specific code blocks and files added for order testing and placeholder rider assignment. Follow these steps to revert the system to its production state.

## 1. Automatic Status Transitions & Rider Assignment

In `src/api/orders/service.py`, locate and remove the block within `confirm_orders_by_cart_ids`.

**File**: [service.py](file:///Users/anush/Projects/nerosoft/celeste-backend/src/api/orders/service.py)

```python
# REMOVE THIS BLOCK (approx. lines 1007-1030)
# ### TESTING ONLY: Auto-transition to PACKED ###
if order.fulfillment_mode != FulfillmentMode.PICKUP.value:
    try:
        # 1. To PROCESSING
        await self.update_order_status(...)
        # 2. To PACKED
        await self.update_order_status(...)
        # 3. Auto-assign Rider
        await self.auto_assign_rider(order.id)
        ...
    except Exception as e:
        ...
# ### END TESTING ONLY ###
```

## 2. Order Sorting (Oldest First for Packed)

In `src/api/orders/service.py`, revert the sorting logic in `get_orders_paginated` to default descending order.

**File**: [service.py](file:///Users/anush/Projects/nerosoft/celeste-backend/src/api/orders/service.py)

```python
# REVERT THIS BLOCK (approx. lines 607-612)
# ### TESTING: PACKED orders should show oldest first ###
if status and len(status) == 1 and status[0] == OrderStatus.PACKED.value:
    order_by_clause = Order.created_at.asc()
else:
    order_by_clause = Order.created_at.desc()
```

**Change back to**:
```python
order_by_clause = Order.created_at.desc()
```

## 3. Rider Assignment Service (Placeholder)

The current rider assignment is a placeholder that assigns `rider_id=2`.

### Files to Delete/Clean
- **Delete File**: `src/api/riders/services/assignment_service.py`
- **In `src/api/orders/service.py`**:
    - Remove `from src.api.riders.services.assignment_service import RiderAssignmentService`
    - Remove `self._rider_assignment_service = RiderAssignmentService()` in `__init__`.
    - Remove the entire `auto_assign_rider(self, order_id: int)` method.

## 4. Pyright Cleanup
After removing the testing logic, you can also remove `from enum import Enum` from the top of `src/api/orders/service.py` if it's no longer used elsewhere in that file.
