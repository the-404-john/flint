struct node
{
    struct node *next;
    int value;
};

struct node_array
{
    struct node *begin, *end;
    struct node *free;
};

void node_array_init( struct node_array *meta,
                      struct node *b, struct node *e )
{
    meta->begin = b;
    meta->end   = e;

    meta->free = b;
    meta->free->next  = NULL;
    meta->free->value = e - b;
}

struct node *node_array_alloc( struct node_array *meta, int count )
{
    struct node *best = NULL;
    struct node **prev;

    for ( struct node **ptr = &meta->free;
          *ptr;
          ptr = &( *ptr )->next )
    {
        if ( ( *ptr )->value >= count &&
             ( !best || ( *ptr )->value < best->value ) )
        {
            best = *ptr;
            prev = ptr;
        }
    }

    if ( !best )
        return NULL;

    int remaining = best->value - count;

    if ( remaining > 0 )
    {
        struct node *ptr = best + count;
        ptr->next  = best->next;
        ptr->value = remaining;
        *prev = ptr;
    }
    else
        *prev = best->next;

    return best;
}

void node_array_free( struct node_array *meta,
                      struct node *node, int size )
{
    node->value = size;
    node->next = meta->free;
    meta->free = node;
}

int abs( int x ) { return x > 0 ? x : -x; }

int main()
{
    enum { array_size = 16 };
    struct node array[ array_size ];
    struct node_array meta;

    node_array_init( &meta, array, array + array_size );

    struct node *p = node_array_alloc( &meta, 3 ),
                *q = node_array_alloc( &meta, 7 ),
                *r = node_array_alloc( &meta, 6 );

    assert( p );
    assert( q );
    assert( r );

    assert( abs( p - q ) >= 3 );
    assert( abs( p - r ) >= 3 );
    assert( abs( q - r ) >= 6 );

    assert( !node_array_alloc( &meta, 1 ) );

    node_array_free( &meta, p, 3 );
    node_array_free( &meta, r, 6 );

    struct node *s = node_array_alloc( &meta, 2 ),
                *t = node_array_alloc( &meta, 6 ),
                *u = node_array_alloc( &meta, 1 );

    assert( s );
    assert( t );
    assert( u );
    assert( !node_array_alloc( &meta, 1 ) );

    return 0;
}

