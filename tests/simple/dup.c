struct node
{
    int value;
    struct node *next;
};

struct heap
{
    struct node *start, *end;
};

struct list
{
    struct node *head;
};

bool dup( struct heap *heap, struct list *in, struct list *out )
{
    struct node *to_use = heap->start,
                *prev = NULL,
                *head;
    int count = 0;

    for ( struct node *n = in->head; n; n = n->next )
    {
        if ( to_use == heap->end )
            return false;

        if ( prev )
            prev->next = to_use;
        else
            head = to_use;

        to_use->value = n->value;
        to_use->next = NULL;

        prev = to_use++;
        ++ count;
    }

    out->head = head;
    heap->start = to_use;
    return true;
}

int main()
{
    enum { heap_size = 64 };
    struct node mem[ heap_size ];
    struct heap heap = { mem, mem + heap_size };

    struct node
        *n_1 = heap.start++,
        *n_2 = heap.start++,
        *n_3 = heap.start++;

    struct list l_1 = { n_1 }, l_2;

    n_1->value = 1;
    n_1->next = n_2;
    n_2->value = 2;
    n_2->next = n_3;
    n_3->value = 3;
    n_3->next = NULL;

    assert( dup( &heap, &l_1, &l_2 ) );
    struct node *n = l_2.head;
    assert( n->value == 1 );
    assert( n = n->next );
    assert( n->value == 2 );
    assert( n = n->next );
    assert( n->value == 3 );
    assert( !n->next );
    assert( heap.start - mem == 6 );

    n_3->next = n_1;
    assert( !dup( &heap, &l_1, &l_2 ) );
    assert( l_2.head->value == 1 );

    return 0;
}

