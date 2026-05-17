int pow_rec( int n, int exp )
{
    assert( exp >= 1 );

    if ( exp == 1 )
        return n;

    if ( exp % 2 == 0 )
        return pow_rec( n * n, exp / 2 );
    else
        return n * pow_rec( n, exp - 1 );
}

int pow_iter( int n, int exp )
{
    assert( exp >= 1 );

    int odd = 1;

    while ( exp > 1 )
    {
        if ( exp % 2 == 1 )
            odd *= n;

        n *= n;
        exp /= 2;
    }

    return n * odd;
}

int main()
{
    assert( pow_rec( 1, 2 ) == 1 );
    assert( pow_rec( 2, 1 ) == 2 );
    assert( pow_rec( 2, 2 ) == 4 );
    assert( pow_rec( 2, 3 ) == 8 );
    assert( pow_rec( 3, 2 ) == 9 );

    for ( int i = 0; i < 32; ++i )
        for ( int j = 1; j < ( i < 8 ? 5 : 4 ); ++j )
            assert( pow_rec( i, j ) == pow_iter( i, j ) );
}

