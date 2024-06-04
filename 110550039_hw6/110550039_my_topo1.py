from mininet.topo import Topo

class MyTopo( Topo ):
    "Custom topology with one switch and four hosts."

    def build( self ):
        "Create custom topology."

        # Add hosts
        h1 = self.addHost( 'h1', ip='10.0.0.1' )
        h2 = self.addHost( 'h2', ip='10.0.0.2' )
        h3 = self.addHost( 'h3', ip='10.0.0.3' )
        h4 = self.addHost( 'h4', ip='10.0.0.4' )

        # Add switch
        s1 = self.addSwitch( 's1' )

        # Add links
        self.addLink( h1, s1 )
        self.addLink( h2, s1 )
        self.addLink( h3, s1 )
        self.addLink( h4, s1 )

# Add the topology to the 'topos' dictionary
topos = { 'mytopo': ( lambda: MyTopo() ) }
