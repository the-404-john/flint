struct matrix_3d
{
    int element[ 9 ];
};

struct mem_area
{
    struct matrix_3d *begin, *end;
    int free_head;
    int unused_count;
};

void matrix_alloc_init( struct mem_area *mem,
                        struct matrix_3d *b, struct matrix_3d *e )
{
    mem->begin = b;
    mem->end = e;

    mem->free_head = -1;
    mem->unused_count = e - b;
}

struct matrix_3d *matrix_alloc( struct mem_area *mem )
{
    if ( mem->free_head >= 0 )
    {
        struct matrix_3d *use = mem->begin + mem->free_head;
        int next_idx = use->element[ 0 ];
        mem->free_head = next_idx;
        return use;
    }

    if ( mem->unused_count > 0 )
    {
        struct matrix_3d *use = mem->end - mem->unused_count;
        mem->unused_count --;
        return use;
    }

    return NULL;
}

void matrix_free( struct mem_area *mem, struct matrix_3d *obj )
{
    obj->element[ 0 ] = mem->free_head;
    mem->free_head = obj - mem->begin;
}

int main()
{
    enum { matrix_count = 60 };
    struct matrix_3d mem[ matrix_count ];
    struct mem_area ma;

    matrix_alloc_init( &ma, mem, mem + matrix_count );

    struct matrix_3d *m_1 = matrix_alloc( &ma );
    assert( m_1 );
    struct matrix_3d *m_2 = matrix_alloc( &ma );
    assert( m_1 != m_2 );

    matrix_free( &ma, m_1 );
    matrix_free( &ma, m_2 );

    struct matrix_3d *matrices[ matrix_count ];

    for ( int repeat = 0; repeat < 2; ++repeat )
    {
        for ( int i = 0; i < matrix_count; ++i )
        {
            matrices[ i ] = matrix_alloc( &ma );
            assert( matrices[ i ] );
            for ( int j = 0; j < 9; ++j )
                matrices[ i ]->element[ j ] = 11;
        }

        assert( !matrix_alloc( &ma ) );

        for ( int i = 0; i < matrix_count; ++i )
            matrix_free( &ma, matrices[ i ] );
    }

    return 0;
}

