"use client"
import * as React from "react";
import { Flex, IconButton, Slider, TextField } from "@radix-ui/themes";

const SLIDER_MIN: number = 0
const SLIDER_MAX: number = 10

export default function RiskFreeRateSlider({ defaultValue }: { defaultValue: number }) {


    const [value, setValue] = React.useState<number>(defaultValue);
    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const newValue = parseFloat(e.target.value);
        if (!isNaN(newValue)) {
            setValue(newValue);
        }
    };

    return (
        <Flex direction="row" align="center" gap="4">

            <TextField.Root>
                <TextField.Slot>
                    r_f
                </TextField.Slot>
                <TextField.Input size="2" value={value.toFixed(2)} onChange={handleInputChange} type="number" />
                <TextField.Slot>
                    <IconButton size="1" variant="ghost">
                        %
                    </IconButton>
                </TextField.Slot>
            </TextField.Root>
            <Slider
                defaultValue={[value * (SLIDER_MAX - SLIDER_MIN)]}
                value={[value * (SLIDER_MAX - SLIDER_MIN)]}
                style={{ width: 300 }}
                draggable
                onValueChange={(value) => value[0] && setValue(value[0] / (SLIDER_MAX - SLIDER_MIN))}
            />
        </Flex>
    );
}