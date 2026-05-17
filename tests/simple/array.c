struct node
{
    int value;
    int next;
};

int list_find( struct node *array, int head, int to_find )
{
    for ( int idx = head; idx >= 0; idx = array[ idx ].next )
        if ( array[ idx ].value == to_find )
            return idx;

    return -1;
}

int main()
{
    struct node array[ 5 ] =
    {
        { 11, 3 },  //      ╭─▶●─╮ 11
        { 10, 0 },  // 10 ●─╯    │
        { 17, 4 },  //           │    17 ●─╮
        { 12, -1 }, //           ╰─▶● 12   │
        { 18, -1 }  //                     ╰─▶● 18
    };

    assert( list_find( array, 1, 12 ) == 3 );
    assert( list_find( array, 1, 10 ) == 1 );
    assert( list_find( array, 0, 12 ) == 3 );
    assert( list_find( array, 0, 10 ) == -1 );

    assert( list_find( array, 2, 17 ) == 2 );
    assert( list_find( array, 2, 18 ) == 4 );

    return 0;
}

