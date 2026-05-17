int set_init();
void set_fini( int set_id );
void set_add( int set_id, unsigned val );
bool set_get( int set_id, unsigned val );

int copy_except( unsigned *values, int value_count,
                 unsigned *except, int except_count,
                 unsigned *out )
{
    int except_set = set_init();

    for ( int i = 0; i < except_count; ++i )
        set_add( except_set, except[ i ] );

    unsigned *start = out;

    for ( int i = 0; i < value_count; ++i )
        if ( !set_get( except_set, values[ i ] ) )
            *out++ = values[ i ];

    set_fini( except_set );

    return out - start;
}

int main()
{
    unsigned in_1[] = { 1, 2, 3, 4, 5, 6 };
    unsigned in_2[] = { 1, 2, 1, 3, 1, 4, 1, 5, 1, 7 };
    unsigned except[] = { 1, 3, 5 };
    unsigned out[ 6 ];

    assert( copy_except( in_1, 6, except, 3, out ) == 3 );
    assert( out[ 0 ] == 2 );
    assert( out[ 1 ] == 4 );
    assert( out[ 2 ] == 6 );

    assert( copy_except( in_2, 10, except, 3, out ) == 3 );
    assert( out[ 0 ] == 2 );
    assert( out[ 1 ] == 4 );
    assert( out[ 2 ] == 7 );

    return 0;
}

enum
{
    SET_INSTANCES = 16,
    SET_CHAR_BIT = 8,
    SET_MAP_CHARS = 32,
    SET_MAX_VAL = SET_MAP_CHARS * SET_CHAR_BIT - 1
};

struct set_map
{
    unsigned char bitmap[SET_MAP_CHARS];
};

struct set_store
{
    struct set_map sets[SET_INSTANCES];
    bool set_used[SET_INSTANCES];
};

struct set_store *set_storage()
{
    static struct set_store storage;
    return &storage;
}

int set_init()
{
    struct set_store * const storage = set_storage();

    for ( int set_id_candidate = 0; ; ++set_id_candidate )
    {
        assert( set_id_candidate < SET_INSTANCES );

        if ( !storage->set_used[set_id_candidate] )
        {
            storage->set_used[set_id_candidate] = true;
            return set_id_candidate;
        }
    }
}

void set_fini( int set_id )
{
    assert( set_id >= 0 && set_id < SET_INSTANCES );

    struct set_store * const storage = set_storage();

    assert( storage->set_used[set_id] );

    for ( unsigned i = 0; i < SET_MAP_CHARS; ++i )
    {
        storage->sets[set_id].bitmap[i] = 0x0u;
    }

    storage->set_used[set_id] = false;
}

bool bmap_bit_get( unsigned char *bitmap, unsigned index )
{
    return ( bitmap[ index / SET_CHAR_BIT ] >> index % SET_CHAR_BIT ) & 0x1u;
}

void bmap_bit_flip( unsigned char *bitmap, unsigned index )
{
    bitmap[ index / SET_CHAR_BIT ] ^= 0x1u << ( index % SET_CHAR_BIT );
}

void set_add( int set_id, unsigned val )
{
    if ( set_get( set_id, val ) )
        return;

    bmap_bit_flip( set_storage()->sets[set_id].bitmap, val );
}

bool set_get( int set_id, unsigned val )
{
    assert( set_id >= 0 && set_id < SET_INSTANCES );
    assert( val <= SET_MAX_VAL );

    struct set_store * const storage = set_storage();

    assert( storage->set_used[set_id] );

    return bmap_bit_get( storage->sets[set_id].bitmap, val );
}

