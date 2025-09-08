# Stores Location-Based Implementation Task

## Overview
Implement comprehensive stores management with location-based services, allowing users to find nearby stores within a specified radius from their current location.

## Requirements

### 1. Store Data Structure
Stores must include detailed location information:

```json
{
  "id": "store_uuid",
  "name": "Store Name",
  "description": "Store description and details",
  "address": "123 Main Street, City Name, State, 12345, Country",
  "location": {
    "latitude": 40.7128,
    "longitude": -74.0060,
    "geohash": "dr5regw3p"  // For efficient geo queries
  },
  "contact": {
    "phone": "+1-234-567-8900",
    "email": "store@example.com"
  },
  "hours": {
    "monday": { "open": "09:00", "close": "21:00", "closed": false },
    "tuesday": { "open": "09:00", "close": "21:00", "closed": false },
    "wednesday": { "open": "09:00", "close": "21:00", "closed": false },
    "thursday": { "open": "09:00", "close": "21:00", "closed": false },
    "friday": { "open": "09:00", "close": "22:00", "closed": false },
    "saturday": { "open": "10:00", "close": "22:00", "closed": false },
    "sunday": { "open": "11:00", "close": "20:00", "closed": false }
  },
  "features": ["parking", "wifi", "wheelchair_accessible", "drive_through"],
  "isActive": true,
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

### 2. Location-Based Query Parameters

#### GET /api/stores - Enhanced Parameters:
- `latitude` (float): User's current latitude
- `longitude` (float): User's current longitude  
- `radius` (float): Search radius in kilometers (default: 10km, max: 50km)
- `limit` (int): Maximum stores to return (default: 20, max: 100)
- `isActive` (boolean): Filter by active stores only (default: true)
- `features` (array): Filter by store features
- `includeDistance` (boolean): Include distance calculations (default: true)
- `includeOpenStatus` (boolean): Include is_open_now calculations (default: true)

#### Response Format:
```json
{
  "success": true,
  "data": {
    "stores": [
      {
        "...store_data...",
        "distance": 2.5,  // Distance in km from user location (if includeDistance=true)
        "is_open_now": true,  // Calculated based on current time and store hours (if includeOpenStatus=true)
        "next_change": "22:00"  // Next open/close time (if includeOpenStatus=true)
      }
    ],
    "user_location": {
      "latitude": 40.7128,
      "longitude": -74.0060
    },
    "search_radius": 10,
    "total_found": 15,
    "returned": 15
  }
}
```

### 3. API Endpoints to Implement

#### Core CRUD Operations:
- `GET /api/stores` - Get all stores with location filtering
- `GET /api/stores/{store_id}` - Get specific store details
- `POST /api/stores` - Create new store (Admin only)
- `PUT /api/stores/{store_id}` - Update store (Admin only)
- `DELETE /api/stores/{store_id}` - Delete store (Admin only)

#### Location-Specific Endpoints:
- `GET /api/stores/nearby` - Optimized endpoint for location queries
- `GET /api/stores/{store_id}/distance` - Calculate distance to specific store
- `GET /api/stores/search` - Advanced search with multiple filters

### 4. Technical Implementation Requirements

#### Distance Calculation:
- Use Haversine formula for accurate distance calculations
- Implement efficient geo-spatial queries using Firestore geohashes
- Cache frequently requested locations

#### Geospatial Indexing:
- Generate geohash for each store location for efficient querying
- Use Firestore compound indexes for location + status queries
- Implement bounding box queries for initial filtering

#### Performance Optimizations:
- Use existing caching system (similar to products/categories caching)
- Use pagination for large result sets
- Optimize queries with proper indexing strategy
- Cache frequently requested location combinations

#### Validation & Error Handling:
- Validate latitude/longitude ranges (-90 to 90, -180 to 180)
- Handle invalid coordinates gracefully
- Validate radius limits (max: 50km) and provide meaningful errors
- Handle edge cases (stores exactly on radius boundary)

### 5. Business Logic

#### Store Hours Calculation:
- Calculate `is_open_now` based on current time and store timezone
- Determine `next_change` (next open/close time)
- Handle special cases (24/7 stores, closed stores)

#### Distance Sorting:
- Primary sort by distance (ascending)
- Secondary sort by store name for ties
- Implement efficient sorting algorithms for large datasets

#### Radius Filtering:
- Filter stores within specified radius using precise calculations
- Support different distance units (km, miles)
- Handle edge cases near boundaries

### 6. Data Migration & Seeding

#### Migration Tasks:
1. Add location fields to existing store documents
2. Generate geohashes for existing stores
3. Create necessary Firestore indexes
4. Populate sample store data with realistic coordinates

#### Sample Data Requirements:
- At least 20 sample stores with realistic coordinates
- Cover different geographic areas for testing
- Include various store types and features
- Realistic business hours and contact information

### 7. Testing Requirements

#### Unit Tests:
- Distance calculation accuracy
- Geohash generation and validation
- Store hours calculation logic
- Radius filtering algorithms

#### Integration Tests:
- Location-based API endpoints
- Database queries with location filters
- Error handling for invalid coordinates
- Performance tests with large datasets

#### Manual Testing Scenarios:
- Find stores within 5km of specific coordinates
- Test edge cases (radius = 0, very large radius)
- Verify distance calculations are accurate
- Test store hours calculation across timezones

### 8. Security & Permissions

#### Access Control:
- Public read access for store location queries
- Admin-only access for CRUD operations
- Rate limiting for location-based queries
- Input sanitization for all location parameters

#### Privacy Considerations:
- Don't log user location coordinates
- Implement opt-out mechanisms if needed
- Consider GDPR compliance for location data

### 9. Future Enhancements (Post-MVP)

#### Advanced Features:
- Real-time inventory checking per store
- Store-specific product availability
- Delivery radius calculation
- Route optimization for multiple stores
- Store ratings and reviews integration
- Traffic-aware distance calculations

#### Performance Improvements:
- Enhanced caching for frequently requested locations
- Use Firestore geo queries with compound indexes
- Implement CDN for static store data
- Add background jobs for geohash updates

## Implementation Priority

### Phase 1 (Core):
1. Update store models with location fields
2. Implement basic distance calculation
3. Create location-based query endpoints
4. Add basic validation and error handling

### Phase 2 (Enhanced):
1. Implement geohash-based optimization
2. Add store hours calculation
3. Implement caching layer
4. Add comprehensive testing

### Phase 3 (Advanced):
1. Performance optimizations
2. Advanced filtering options
3. Analytics and monitoring
4. Additional business features

## Success Criteria

### Functional Requirements:
- ✅ Users can find stores within specified radius
- ✅ Distance calculations are accurate (±1% tolerance)
- ✅ Store hours are calculated correctly
- ✅ API responses are properly formatted
- ✅ All CRUD operations work correctly

### Performance Requirements:
- Location queries respond within 500ms
- Support concurrent requests (100+ users)
- Handle datasets up to 10,000 stores
- Memory usage remains reasonable

### Quality Requirements:
- 95%+ test coverage for location features
- Comprehensive error handling
- Clear API documentation
- Proper input validation

## Database Schema Changes

### Firestore Collection: `stores`
```javascript
// Index requirements:
stores.location.geohash (single field, ascending)
stores.isActive (single field, ascending) 
stores.location.geohash + stores.isActive (compound index)
```

### Example Firestore Document:
```json
{
  "name": "Downtown Electronics Store",
  "description": "Premium electronics store with latest gadgets",
  "address": "456 Commerce St, New York, NY 10013, USA",
  "location": {
    "latitude": 40.7209,
    "longitude": -74.0007,
    "geohash": "dr5ru6p83"
  },
  "contact": {
    "phone": "+1-212-555-0123",
    "email": "downtown@electronics.com"
  },
  "hours": {
    "monday": { "open": "09:00", "close": "21:00", "closed": false },
    "tuesday": { "open": "09:00", "close": "21:00", "closed": false },
    "wednesday": { "open": "09:00", "close": "21:00", "closed": false },
    "thursday": { "open": "09:00", "close": "21:00", "closed": false },
    "friday": { "open": "09:00", "close": "22:00", "closed": false },
    "saturday": { "open": "10:00", "close": "22:00", "closed": false },
    "sunday": { "open": "11:00", "close": "20:00", "closed": false }
  },
  "features": ["parking", "wifi", "wheelchair_accessible"],
  "isActive": true,
  "created_at": "2025-01-15T10:30:00.000Z",
  "updated_at": "2025-01-15T10:30:00.000Z"
}
```

## Notes
- All coordinates use WGS84 datum (standard GPS coordinates)
- Distance calculations use kilometers by default
- Store hours are in 24-hour format in store's local timezone
- Geohash precision: 9 characters (±2.4m accuracy)
- Default search radius: 10km, maximum: 50km
- Address stored as single string for simplicity
- Cache system follows existing patterns from products/categories services