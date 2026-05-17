unsigned permute( unsigned n );

unsigned find_period( unsigned initial )
{
    unsigned last = initial;
    unsigned length = 0;

    do
    {
        ++ length;
        last = permute( last );
    }
    while ( last != initial );

    return length;
}

int main()
{
    assert( find_period( 1 ) == 3 );
    assert( find_period( 5 ) == 3 );
    assert( find_period( 14 ) == 13 );

    return 0;
}

unsigned permute( unsigned n )
{
    if ( n < 13 )
        return n / 3 * 3 + ( n + 1 ) % 3;
    else
        return n / 13 * 13 + ( n + 1 ) % 13;
}

