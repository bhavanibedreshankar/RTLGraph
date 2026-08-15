module top (
    input  wire clk,
    input  wire rst_n,
    input  wire en,
    output wire tick
);
    wire [3:0] count_w;

    counter u_counter (
        .clk   (clk),
        .rst_n (rst_n),
        .en    (en),
        .count (count_w)
    );

    decoder u_decoder (
        .count (count_w),
        .tick  (tick)
    );
endmodule
