# Backpropagation Visual Guide

## The Problem: Credit Assignment

When the network makes a wrong prediction, we know the **output layer's error** (expected - actual). But what about the **hidden layer**? There's no "expected output" for hidden neurons.

**The solution:** Propagate errors backward through the weights.

---

## Forward Pass (left to right)

Data flows from inputs through hidden layer to output layer.

```
    INPUTS              HIDDEN LAYER           OUTPUT LAYER
    [0,2,2,0,2,0]          (6 neurons)            (8 neurons)
         │                     │                      │
         │    ┌────────────────┼───────────────┐      │
         │    │                │               │      │
         ▼    ▼                ▼               ▼      ▼
        ┌──┐ ┌──┐            ┌──┐            ┌──┐   ┌──┐
        │H0│ │H1│ ...        │H5│            │O0│...│O7│
        └──┘ └──┘            └──┘            └──┘   └──┘
          │    │               │               ▲      ▲
          │    │               │               │      │
          └────┴───────────────┴───────────────┴──────┘
                    (weights connect every H to every O)
```

---

## Backward Pass (right to left)

Errors flow from output layer back to hidden layer, **scaled by weights**.

```
                                           EXPECTED: [0,0,0,0,1,0,0,0] (Cat)
                                           ACTUAL:   [0.2,0.3,0.1,0.1,0.6,0.2,0.1,0.1]
                                                            │
                                                            ▼
    INPUTS              HIDDEN LAYER           OUTPUT ERRORS
                                              O0: -0.2  (0 - 0.2)
         │                  H0◄────────────── O1: -0.3
         │                    ◄─────────┐     O2: -0.1
         │                    ◄────┐    │     O3: -0.1
         │                         │    │     O4: +0.4  ★ (1 - 0.6)
         │                  H1◄────┼────┼──── O5: -0.2
         │                         │    │     O6: -0.1
         │                         │    │     O7: -0.1
```

---

## The Key Insight: Blame is Proportional to Connection Strength

```
             weight = 0.9 (strong connection)
        H0 ═══════════════════════════════► O4 (error: +0.4)

             weight = 0.1 (weak connection)
        H1 ───────────────────────────────► O4 (error: +0.4)


    H0's blame from O4: 0.4 × 0.9 = 0.36  (BIG - strong connection)
    H1's blame from O4: 0.4 × 0.1 = 0.04  (small - weak connection)
```

If a hidden neuron has a **strong weight** to an output neuron with a **big error**, that hidden neuron gets more blame.

---

## Hidden Error Formula

For each hidden neuron `h`:

```
hiddenError[h] = Σ (outputError[o] × weight[h→o])
                 for all output neurons o
```

In code:

```csharp
for (int h = 0; h < hiddenLayer.Count; h++)        // For each hidden neuron
{
    hiddenErrors[h] = 0.0;
    for (int o = 0; o < outputLayer.Count; o++)    // Sum blame from ALL outputs
    {
        hiddenErrors[h] += outputErrors[o] * outputLayer[o].Weights[h];
    }
}
```

---

## Full Backpropagation Algorithm

```
1. FORWARD PASS
   - Compute hidden layer outputs from inputs
   - Compute final outputs from hidden outputs
   - Save both for later

2. CALCULATE OUTPUT ERRORS
   - outputError[i] = expected[i] - actual[i]

3. BACKPROPAGATE TO HIDDEN LAYER
   - hiddenError[h] = Σ (outputError[o] × weight[h→o])

4. UPDATE WEIGHTS
   - Output neurons: Train with hiddenOutputs and outputErrors
   - Hidden neurons: Train with original inputs and hiddenErrors
```

---

## Why It's Called "Backpropagation"

The error signal **propagates backward** through the network:

```
Output Error → (× weights) → Hidden Error → (× weights) → [next layer if any]
```

Each layer asks: "How much did I contribute to the downstream error?"

The answer flows backward through the same weights that carried signals forward.

---

## The Symmetry

| Forward Pass | Backward Pass |
|--------------|---------------|
| Signals flow through weights | Errors flow through same weights |
| Input → Hidden → Output | Output → Hidden → Input |
| Weights amplify signals | Weights distribute blame |
