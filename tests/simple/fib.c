int fib( int n )
{
    int a = 1, b = 1;

    for ( int i = 0; i < n - 2; ++i )
    {
        int c = a + b;
        a = b;
        b = c;
    }

    return b;
}

int main()
{
    assert( fib( 1 ) == 1 );
    assert( fib( 2 ) == 1 );
    assert( fib( 7 ) == 13 );
    assert( fib( 20 ) == 6765 );

    return 0;
}
