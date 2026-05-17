bool divmod( int dividend, int divisor, int *quotient, int *modulus )
{
    if ( divisor == 0 )
        return false;

    *quotient = dividend / divisor;
    *modulus = dividend % divisor;

    return true;
}

int main()
{
    int quot, mod;

    assert( divmod( 1, 1, &quot, &mod ) );
    assert( quot == 1 );
    assert( mod == 0 );

    assert( !divmod( 1, 0, &quot, &mod ) );

    return 0;
}

