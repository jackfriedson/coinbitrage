

def order_book(msg, *args):
    return {
        'time': msg[3],
        'pair': msg[1],
        'bid': max([float(b[0]) for b in msg[2]['bids']]),
        'ask': min([float(a[0]) for a in msg[2]['asks']])
    }