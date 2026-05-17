bool is_prime( unsigned number )
{
    if ( number < 2 )
        return false;

    unsigned divisor = 2;
    unsigned sqrt_uint_max = 1 << sizeof( unsigned ) * 4;

    while ( divisor <= sqrt_uint_max &&
            divisor * divisor <= number )
    {

        if ( number % divisor == 0 )
            return false;

        ++ divisor;
    }

    return true;
}

int main()
{
    assert( is_prime( 2 ) );
    assert( is_prime( 3 ) );
    assert( is_prime( 5 ) );
    assert( is_prime( 13 ) );
    assert( is_prime( 29 ) );
    assert( is_prime( 97 ) );
    assert( is_prime( 619 ) );

    assert( !is_prime( 1 ) );
    assert( !is_prime( 4 ) );
    assert( !is_prime( 6 ) );
    assert( !is_prime( 8 ) );
    assert( !is_prime( 68 ) );
    assert( !is_prime( 77 ) );
    assert( !is_prime( 81 ) );
    assert( !is_prime( 323 ) );
    assert( !is_prime( 36863u ) );

    assert( is_prime( 65521u ) );
}
