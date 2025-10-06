# Inventory Lifecycle Documentation

## Inventory Fields

Each inventory record tracks three critical quantities:

```python
quantity_available   # Items physically in stock and available to order
quantity_on_hold     # Items held for pending orders (payment not confirmed)
quantity_reserved    # Items reserved for confirmed orders (not yet shipped)
```

**Total Stock** = `quantity_available + quantity_on_hold + quantity_reserved`

## Is In Stock Calculation

```python
in_stock = quantity_available > 0
```

This is **correct** because:
- Only `quantity_available` represents items customers can actually order
- Items on hold/reserved are already committed to other orders
- When a customer views products, they should only see what's truly available

## Complete Order Lifecycle

### Example: Store has 100 units of Product A

**Initial State:**
```
quantity_available: 100
quantity_on_hold: 0
quantity_reserved: 0
is_in_stock: true
```

---

### 1. Customer Places Order (Checkout)

**Code:** `orders/service.py:489` → `inventory_service.place_hold()`

**What Happens:**
- Customer orders 10 units
- Order created with status: `PENDING`
- Inventory hold placed

**Inventory Transaction:**
```python
quantity_available: -10  (100 → 90)
quantity_on_hold: +10    (0 → 10)
```

**After State:**
```
quantity_available: 90
quantity_on_hold: 10
quantity_reserved: 0
is_in_stock: true  (90 > 0)
```

**Why?** The 10 units are temporarily held while waiting for payment confirmation.

---

### 2A. Payment Successful (Callback: status_code = "2")

**Code:** `orders/service.py:570-572` → `update_order_status(CONFIRMED)`

**What Happens:**
- Payment gateway confirms payment
- Order status: `PENDING` → `CONFIRMED`
- Hold converted to reservation

**Inventory Transaction (via `confirm_reservation`):**
```python
quantity_on_hold: -10    (10 → 0)
quantity_reserved: +10   (0 → 10)
```

**After State:**
```
quantity_available: 90
quantity_on_hold: 0
quantity_reserved: 10
is_in_stock: true  (90 > 0)
```

**Why?** Items move from temporary hold to confirmed reservation because payment succeeded.

---

### 2B. Payment Failed (Callback: status_code ≠ "2")

**Code:** `orders/service.py:593-595` → `update_order_status(CANCELLED)`

**What Happens:**
- Payment gateway reports failure
- Order status: `PENDING` → `CANCELLED`
- Hold released back to available

**Inventory Transaction (via `release_hold`):**
```python
quantity_available: +10  (90 → 100)
quantity_on_hold: -10    (10 → 0)
```

**After State:**
```
quantity_available: 100
quantity_on_hold: 0
quantity_reserved: 0
is_in_stock: true  (100 > 0)
```

**Why?** Payment failed, so items return to available stock for other customers.

---

### 3. Order Shipped

**Code:** `orders/service.py:392-397` → `update_order_status(SHIPPED)`

**What Happens:**
- Warehouse ships the order
- Order status: `CONFIRMED` → `SHIPPED`
- Reserved items removed from inventory

**Inventory Transaction (via `fulfill_order`):**
```python
quantity_reserved: -10   (10 → 0)
```

**After State:**
```
quantity_available: 90
quantity_on_hold: 0
quantity_reserved: 0
is_in_stock: true  (90 > 0)
```

**Why?** Items physically left the warehouse, so they're removed from total inventory.

---

## Multi-Store Order Example

When an order spans multiple stores, each item tracks its store:

**Order Details:**
- Order #1 (Main store: Store A)
  - Item 1: Product A, Qty 5, **store_id: 1** (Store A)
  - Item 2: Product B, Qty 3, **store_id: 2** (Store B)
  - Item 3: Product C, Qty 2, **store_id: 1** (Store A)

**Checkout (Place Hold):**
```
Store A (id: 1):
  Product A: quantity_available -5, quantity_on_hold +5
  Product C: quantity_available -2, quantity_on_hold +2

Store B (id: 2):
  Product B: quantity_available -3, quantity_on_hold +3
```

**Payment Success (Confirm Reservation):**
```
Store A (id: 1):
  Product A: quantity_on_hold -5, quantity_reserved +5
  Product C: quantity_on_hold -2, quantity_reserved +2

Store B (id: 2):
  Product B: quantity_on_hold -3, quantity_reserved +3
```

**Key Fix (2025-09-29):**
- Previously: Used `order.store_id` for ALL items (WRONG!)
- Now: Uses `item.store_id` for each item (CORRECT!)
- This ensures holds/reservations are released from the correct stores

---

## Inventory Transaction Service Methods

### `place_hold(product_id, store_id, quantity)`
```python
available_change: -quantity
on_hold_change: +quantity
```
Called during checkout when order is created.

### `release_hold(product_id, store_id, quantity)`
```python
available_change: +quantity
on_hold_change: -quantity
```
Called when payment fails or order is cancelled before confirmation.

### `confirm_reservation(product_id, store_id, quantity)`
```python
on_hold_change: -quantity
reserved_change: +quantity
```
Called when payment succeeds and order is confirmed.

### `fulfill_order(product_id, store_id, quantity)`
```python
reserved_change: -quantity
```
Called when order is shipped (items physically leave warehouse).

---

## Error Cases

### "Insufficient stock for this operation"
- Occurs when: `quantity_available` would go negative
- Reason: Not enough available stock to place hold
- Solution: Customer needs to reduce order quantity

### "Cannot release more items than are on hold"
- Occurs when: `quantity_on_hold` would go negative
- Reason: Trying to release more than what's held (was the bug!)
- Solution: Ensure correct `store_id` is used for each item

### "Cannot release more items than are reserved"
- Occurs when: `quantity_reserved` would go negative
- Reason: Trying to fulfill more than what's reserved
- Solution: Check order confirmation state

---

## Validation Rules

All operations are validated in `inventory/services/transaction_service.py:44-49`:

```python
if new_available < 0:
    raise ValidationException("Insufficient stock for this operation.")
if new_on_hold < 0:
    raise ValidationException("Cannot release more items than are on hold.")
if new_reserved < 0:
    raise ValidationException("Cannot release more items than are reserved.")
```

These constraints ensure inventory integrity at the database level.

---

## Summary

| Order Status | Inventory State | Customer View |
|-------------|----------------|---------------|
| N/A | `available: 100` | ✅ In Stock (100 available) |
| PENDING | `available: 90, on_hold: 10` | ✅ In Stock (90 available) |
| CONFIRMED | `available: 90, reserved: 10` | ✅ In Stock (90 available) |
| SHIPPED | `available: 90` | ✅ In Stock (90 available) |
| CANCELLED | `available: 100` | ✅ In Stock (100 available) |

**Key Insight:** Customers always see `quantity_available` as the true "in stock" count, which automatically excludes items held or reserved by other orders.
