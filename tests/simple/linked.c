int list_find( int *next, int *value, int head, int to_find )
{
    for ( int idx = head; idx >= 0; idx = next[ idx ] )
        if ( value[ idx ] == to_find )
            return idx;

    return -1;
}

int main()
{
    int next[] =
    {
         3,  //      ╭─▶●─╮ 11
         0,  // 10 ●─╯    │
         4,  //           │    17 ●─╮
         -1, //           ╰─▶● 12   │
         -1  //                     ╰─▶● 18
    };

    int value[] = { 11, 10, 17, 12, 18 };

    assert( list_find( next, value, 1, 12 ) == 3 );
    assert( list_find( next, value, 1, 10 ) == 1 );
    assert( list_find( next, value, 0, 12 ) == 3 );
    assert( list_find( next, value, 0, 10 ) == -1 );

    assert( list_find( next, value, 2, 17 ) == 2 );
    assert( list_find( next, value, 2, 18 ) == 4 );

    return 0;
}


