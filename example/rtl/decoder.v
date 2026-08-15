module decoder (
    input  wire [3:0] count,
    output wire        tick
);
    assign tick = (count == 4'd15);
endmodule
