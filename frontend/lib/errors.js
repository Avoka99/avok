export function translateApiError(errorMessage) {
  if (!errorMessage) {
    return "An unexpected error occurred. Please try again.";
  }

  const errorMap = {
    "Order blocked due to high fraud risk": "Your order is being reviewed for security. Our team will contact you within 24 hours.",
    "Payment blocked due to security concerns": "We couldn't process your payment. Please contact our support team for help.",
    "High-value guest checkout requires email": "Please provide your email address to complete this purchase.",
    "Unable to create checkout session": "We couldn't verify your account. Please try again or contact support.",
    "Phone number already belongs to an Avok account": "This phone number is registered. Please sign in to continue.",
    "Insufficient verified account balance": "Your Avok balance is insufficient. Please add funds or use a different payment method.",
    "Invalid OTP": "The code you entered is incorrect. Please try again.",
    "OTP has expired": "Your code has expired. Please request a new one.",
    "Cannot release funds for order in status": "This order cannot be completed in its current state.",
    "Refund already exists for this checkout session": "A refund has already been processed for this order.",
    "Only payers can create checkout sessions": "Only buyers can create checkout sessions.",
    "Only the payer can fund this checkout session": "Only the original buyer can fund this session.",
  };

  const lowerMessage = errorMessage.toLowerCase();
  
  for (const [key, value] of Object.entries(errorMap)) {
    if (lowerMessage.includes(key.toLowerCase())) {
      return value;
    }
  }

  if (lowerMessage.includes("failed") || lowerMessage.includes("error")) {
    return "Something went wrong. Please try again or contact support if the problem persists.";
  }

  return errorMessage;
}

export function getErrorAction(errorMessage) {
  if (!errorMessage) return null;

  const lowerMessage = errorMessage.toLowerCase();
  
  if (lowerMessage.includes("support") || lowerMessage.includes("contact")) {
    return {
      label: "Contact Support",
      action: "mailto:support@avok.com"
    };
  }

  if (lowerMessage.includes("sign in") || lowerMessage.includes("login")) {
    return {
      label: "Sign In",
      action: "/login"
    };
  }

  if (lowerMessage.includes("verify") || lowerMessage.includes("kyc")) {
    return {
      label: "Verify Account",
      action: "/account"
    };
  }

  return null;
}
