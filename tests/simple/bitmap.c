bool is_set( unsigned char *bitmap, int idx )
{
    unsigned char mask = 1u << ( idx % 8 );
    return bitmap[ idx / 8 ] & mask;
}

void set( unsigned char *bitmap, int idx )
{
    unsigned char mask = 1u << ( idx % 8 );
    bitmap[ idx / 8 ] |= mask;
}

void sieve( unsigned char *bitmap, int count )
{
    for ( int i = 2; i < count; ++i )
        for ( int j = 2 * i; j < count; j += i )
            set( bitmap, j );
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

    unsigned char bitmap[ count / 8 ] = { 0 };

    sieve( bitmap, count );

    for ( int i = 2; i < count; ++i )
        assert( is_prime( i ) == !is_set( bitmap, i ) );

    return 0;
}
