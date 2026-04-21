// import
import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

// detect the environment of this deployment
export const detectEnvironment = (host) => {
    let environment = host.trim().replace(/\.+$/, '');
    if (environment.includes('localhost')) {
        environment = "local";
    } else {
        environment = import.meta.env.MODE;
    }
    return(environment);
};

// format date values
export const formatDateValue = (v) => {
    return v.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "numeric",
        hour12: !1
        })
        .split(",")
        .join("\n");
}
