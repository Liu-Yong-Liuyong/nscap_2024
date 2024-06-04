from mininet.topo import Topo

class MyTopo( Topo ):
    "Custom topology with one switch and four hosts."

    def build( self ):
        "Create custom topology."

        # Add hosts
        h5 = self.addHost( 'h5', ip='10.0.0.5' )
        h6 = self.addHost( 'h6', ip='10.0.0.6' )
        h7 = self.addHost( 'h7', ip='10.0.0.7' )
        h8 = self.addHost( 'h8', ip='10.0.0.8' )

        # Add switch
        s2 = self.addSwitch( 's2' )

        # Add links
        self.addLink( h5, s2 )
        self.addLink( h6, s2 )
        self.addLink( h7, s2 )
        self.addLink( h8, s2 )

# Add the topology to the 'topos' dictionary
topos = { 'mytopo': ( lambda: MyTopo() ) }
