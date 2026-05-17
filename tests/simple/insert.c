struct node
{
    int value;
    struct node *next;
};

struct list
{
    struct node *head;
};

bool list_insert( struct list *list, int index,
                  struct node *to_link )
{
    struct node **link = &list->head;

    while ( *link && index-- > 0 )
        link = &( *link )->next;

    if ( index > 0 )
        return false;

    to_link->next = *link;
    *link = to_link;
    return true;
}

int main()
{
    struct list lst = { NULL };

    struct node n1 = { 1, NULL };
    struct node n2 = { 2, NULL };
    struct node n3 = { 3, NULL };
    struct node n4 = { 3,  &n3 };

    assert( !list_insert( &lst, 1, &n1 ) );
    assert( list_insert( &lst, 0, &n1 ) );
    assert( lst.head == &n1 );
    assert( lst.head->next == NULL );

    assert( !list_insert( &lst, 2, &n2 ) );
    assert( list_insert( &lst, 0, &n2 ) );
    assert( lst.head == &n2 );
    assert( lst.head->next = &n1 );
    assert( lst.head->next->next == NULL );

    assert( !list_insert( &lst, 3, &n2 ) );
    assert( list_insert( &lst, 1, &n4 ) );
    assert( lst.head == &n2 );
    assert( lst.head->next == &n4 );
    assert( lst.head->next->next == &n1 );

    return 0;
}

