void sieve( bool *composite, int count )
{
    for ( int i = 2; i < count; ++i )
        for ( int j = 2 * i; j < count; j += i )
            composite[ j ] = true;
}

bool is_prime( int n )
{
    for ( int i = 2; i < n; ++i )
        if ( n % i == 0 )
            return false;

    return true;
}

int main()
{
    enum { count = 128 };

    bool composite[ count ] = { false };
    sieve( composite, count );

    assert( !composite[ 2 ] );
    assert( !composite[ 3 ] );
    assert(  composite[ 4 ] );
    assert( !composite[ 5 ] );
    assert(  composite[ 6 ] );
    assert( !composite[ 7 ] );
    assert(  composite[ 8 ] );

    for ( int i = 2; i < count; ++i )
        assert( is_prime( i ) == !composite[ i ] );

    return 0;
}

