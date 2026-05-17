bool divmod( int dividend, int divisor, int *quotient, int *modulus )
{
    if ( divisor == 0 )
        return false;

    if ( quotient )
        *quotient = dividend / divisor;
    if ( modulus )
        *modulus = dividend % divisor;

    return true;
}

int main()
{
    int quot, mod;

    assert( divmod( 1, 1, NULL, &mod ) );
    assert( mod == 0 );
    assert( divmod( 1, 2, &quot, &mod ) );
    assert( quot == 0 );
    assert( mod == 1 );
    assert( divmod( 3, 2, &quot, NULL ) );
    assert( quot == 1 );

    return 0;
}

